from __future__ import annotations

from ._support_shared import *  # noqa: F403
from .record_signals import _object_dict, _object_list, _safe_int


def infer_surface(url: str, explicit_surface: object | None = None) -> str:
    explicit = str(explicit_surface or "").strip().lower()
    if explicit:
        return explicit
    normalized_url = str(url or "").strip().lower()
    parsed_url = urlsplit(normalized_url)
    host = str(parsed_url.hostname or "").strip().lower()
    host_label = host.removeprefix("www.").split(".", 1)[0]
    path_segments = [segment for segment in parsed_url.path.split("/") if segment]
    family = detect_platform_family(normalized_url)
    job_surface = _inferred_job_surface(normalized_url, host, host_label, family)
    if job_surface:
        return job_surface
    if _looks_like_ecommerce_detail(normalized_url, host, host_label, path_segments):
        return "ecommerce_detail"
    return "ecommerce_listing"


def _inferred_job_surface(
    normalized_url: str,
    host: str,
    host_label: str,
    family: str,
) -> str | None:
    if (
        family in job_platform_families()
        or host.endswith(".jobs")
        or host.endswith(("startup.jobs", ".usajobs.gov"))
        or host == "usajobs.gov"
    ):
        if any(token in normalized_url for token in _JOB_LISTING_HINTS):
            return "job_listing"
        detail_hints = ("/job/", "/viewjob", "showjob=")
        return (
            "job_detail"
            if any(token in normalized_url for token in detail_hints)
            else "job_listing"
        )
    if any(token in host_label for token in ("job", "career")) and not any(
        token in normalized_url for token in _DETAIL_HINTS
    ):
        return "job_listing"
    if any(token in normalized_url for token in _JOB_LISTING_HINTS):
        return "job_listing"
    return None


def _looks_like_ecommerce_detail(
    normalized_url: str,
    host: str,
    host_label: str,
    path_segments: list[str],
) -> bool:
    if (
        host == "autozone.com" or host.endswith(".autozone.com")
    ) and normalized_url.rstrip("/").rsplit("/", 1)[-1].count("_") >= 2:
        return True
    if (
        len(path_segments) >= 2
        and path_segments[-1] == "index.html"
        and _DETAIL_SLUG_WITH_ID_RE.fullmatch(path_segments[-2])
    ):
        return True
    if any(token in normalized_url for token in _DETAIL_HINTS):
        return True
    terminal = path_segments[-1].lower() if path_segments else ""
    if (
        _DETAIL_FILE_RE.fullmatch(terminal)
        and not _NON_DETAIL_FILE_RE.fullmatch(terminal)
        and any(separator in terminal for separator in ("-", "_"))
        and not any(
            token in terminal for token in ("jobs", "careers", "category", "collection")
        )
    ):
        return True
    if (
        len(path_segments) == 1
        and _PRODUCT_LIKE_TERMINAL_SLUG_RE.fullmatch(terminal)
        and host_label
        and host_label in terminal
    ):
        return True
    return False


def build_explicit_sites(
    urls: list[str],
    *,
    explicit_surfaces: list[str] | None = None,
) -> list[dict[str, str]]:
    normalized_urls = [
        str(value or "").strip() for value in (urls or []) if str(value or "").strip()
    ]
    normalized_surfaces = [
        str(value or "").strip()
        for value in (explicit_surfaces or [])
        if str(value or "").strip()
    ]
    if normalized_surfaces and len(normalized_surfaces) != len(normalized_urls):
        raise ValueError("Explicit URL and surface counts must match")
    rows: list[dict[str, str]] = []
    for index, url in enumerate(normalized_urls):
        explicit_surface = (
            normalized_surfaces[index] if index < len(normalized_surfaces) else ""
        )
        rows.append(
            {
                "name": url,
                "url": url,
                "surface": infer_surface(url, explicit_surface=explicit_surface),
            }
        )
    return rows


def load_site_set(path: Path, *, site_set_name: str) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in site set file {path}: {exc.msg}") from exc
    defaults, sites = _site_manifest(payload, path=path, site_set_name=site_set_name)
    return [row for item in sites if (row := _site_row(defaults, item)) is not None]


def _site_manifest(
    payload: object,
    *,
    path: Path,
    site_set_name: str,
) -> tuple[dict[str, object], list[object]]:
    if isinstance(payload, dict) and isinstance(payload.get("site_sets"), dict):
        site_set = payload["site_sets"].get(site_set_name)
        if not isinstance(site_set, dict):
            raise ValueError(f"Unknown site set: {site_set_name}")
        defaults = _object_dict(site_set.get("defaults"))
        sites = site_set.get("sites")
        if not isinstance(sites, list):
            raise ValueError(f"Site set {site_set_name} has no sites list")
    elif isinstance(payload, dict) and isinstance(payload.get("sites"), list):
        manifest_name = str(payload.get("name") or path.stem).strip()
        if site_set_name not in {"", manifest_name, path.stem}:
            raise ValueError(f"Unknown site set: {site_set_name}")
        defaults = _object_dict(payload.get("defaults"))
        sites = payload["sites"]
    else:
        raise ValueError(f"Invalid site-set payload in {path}")
    return defaults, sites


def _site_row(defaults: dict[str, object], item: object) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    site = {**defaults, **item}
    url = str(item.get("url") or "").strip()
    if not url:
        return None
    row: dict[str, object] = {
        "name": str(site.get("name") or url).strip(),
        "url": url,
        "surface": infer_surface(
            url,
            explicit_surface=site.get("surface"),
        ),
        "bucket": str(site.get("bucket") or "").strip().lower() or None,
        "expected_failure_modes": [
            str(value).strip()
            for value in _object_list(site.get("expected_failure_modes"))
            if str(value).strip()
        ],
        "artifact_run_id": _safe_int(site.get("artifact_run_id")) or None,
        "seed_failure_mode": str(site.get("seed_failure_mode") or "").strip().lower()
        or None,
        "quality_expectations": {
            **_object_dict(defaults.get("quality_expectations")),
            **_object_dict(item.get("quality_expectations")),
        },
    }
    optional_values = {
        "gate": str(site.get("gate") or "").strip().lower() or None,
        "expected": _object_dict(site.get("expected")) or None,
        "known_failure_mode": str(site.get("known_failure_mode") or "").strip() or None,
    }
    row.update({key: value for key, value in optional_values.items() if value})
    return row


def parse_test_sites_markdown(path: Path, *, start_line: int) -> list[dict[str, str]]:
    if not isinstance(start_line, int) or start_line < 1:
        raise ValueError("parse_test_sites_markdown start_line must be an integer >= 1")
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[start_line - 1 :]:
        value = html.unescape(str(line or "").strip())
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            rows.append({"name": value, "url": value, "surface": infer_surface(value)})
            continue
        if not value.startswith("|") or "http" not in value:
            continue
        cells = [cell.strip() for cell in value.strip("|").split("|")]
        url = ""
        explicit_surface = ""
        name = ""
        for index, cell in enumerate(cells):
            match = re.search(r"https?://[^`\s|>]+", cell)
            if match is not None and not url:
                url = match.group(0).strip().rstrip("`")
                name = url
            if not explicit_surface and index > 0:
                normalized = re.sub(
                    r"[^a-z0-9]+", "_", str(cell or "").strip().lower()
                ).strip("_")
                if normalized in {
                    "listing",
                    "ajax_listing",
                    "infinite_scroll",
                    "spa_listing",
                    "detail",
                    "spa_detail",
                }:
                    explicit_surface = {
                        "listing": "ecommerce_listing",
                        "ajax_listing": "ecommerce_listing",
                        "infinite_scroll": "ecommerce_listing",
                        "spa_listing": "ecommerce_listing",
                        "detail": "ecommerce_detail",
                        "spa_detail": "ecommerce_detail",
                    }[normalized]
                    break
        if url:
            rows.append(
                {
                    "name": name or url,
                    "url": url,
                    "surface": infer_surface(url, explicit_surface=explicit_surface),
                }
            )
    return rows


def unavailable_configured_adapters() -> set[str]:
    return set(configured_adapter_names()) - {
        adapter.name for adapter in registered_adapters()
    }


def timeout_owner_for_mode(mode: str) -> str:
    return (
        "batch_runtime" if mode == HARNESS_MODE_FULL_PIPELINE else "acquisition_runtime"
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
