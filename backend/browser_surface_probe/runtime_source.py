from __future__ import annotations

from ._core_shared import *  # noqa: F403


@dataclass(slots=True)
class RuntimeSource:
    source_kind: str
    run_id: int | None
    identity_run_id: int
    proxy_list: list[str]
    proxy_profile: dict[str, object]
    locality_profile: dict[str, object]
    selected_proxy: str | None
    selected_proxy_index: int | None
    browser_engine: str

def _normalize_space(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()

def _normalize_key(value: object) -> str:
    return _NON_ALNUM_RE.sub(" ", _normalize_space(value).lower()).strip()

def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True, default=str)

def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

def _coerce_proxy_profile(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}

def _int_list(value: object) -> list[int]:
    return [item for item in _object_list(value) if isinstance(item, int)]

def _dict_rows(value: object) -> list[dict[str, object]]:
    return [
        _object_dict(item) for item in _object_list(value) if isinstance(item, dict)
    ]

def _coerce_locality_profile(
    *,
    geo_country: object = None,
    language_hint: object = None,
    currency_hint: object = None,
) -> dict[str, object]:
    normalized_geo = _normalize_space(geo_country).upper() or "auto"
    if len(normalized_geo) != 2 or not normalized_geo.isalpha():
        normalized_geo = "auto"
    normalized_language = _normalize_space(language_hint) or None
    normalized_currency = _normalize_space(currency_hint) or None
    return {
        "geo_country": normalized_geo,
        "language_hint": normalized_language,
        "currency_hint": normalized_currency,
    }

async def _load_run_runtime_source(
    run_id: int, *, browser_engine: str
) -> RuntimeSource:
    async with SessionLocal() as session:
        run = await get_run(session, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    settings_view = run.settings_view
    proxy_list = settings_view.proxy_list()
    proxy_profile = settings_view.proxy_profile()
    locality_profile = settings_view.locality_profile()
    enabled = bool(proxy_profile.get("enabled"))
    selected_proxy = proxy_list[0] if enabled and proxy_list else None
    selected_proxy_index = 0 if selected_proxy is not None else None
    return RuntimeSource(
        source_kind="run",
        run_id=run.id,
        identity_run_id=run.id,
        proxy_list=proxy_list,
        proxy_profile=proxy_profile,
        locality_profile=locality_profile,
        selected_proxy=selected_proxy,
        selected_proxy_index=selected_proxy_index,
        browser_engine=browser_engine,
    )

def _load_explicit_runtime_source(
    *,
    proxies: list[str],
    proxy_profile_path: str | None,
    locality_profile: dict[str, object],
    browser_engine: str,
) -> RuntimeSource:
    proxy_profile: dict[str, object] = {}
    if proxy_profile_path:
        raw = json.loads(Path(proxy_profile_path).read_text(encoding="utf-8"))
        proxy_profile = _coerce_proxy_profile(raw)
    proxy_list = [
        _normalize_space(value) for value in proxies if _normalize_space(value)
    ]
    enabled = bool(proxy_list) or bool(proxy_profile.get("enabled"))
    if enabled:
        proxy_profile = dict(proxy_profile)
        proxy_profile["enabled"] = True
        proxy_profile["proxy_list"] = proxy_list
    selected_proxy = proxy_list[0] if proxy_list else None
    selected_proxy_index = 0 if selected_proxy is not None else None
    identity_run_id = time.time_ns()
    return RuntimeSource(
        source_kind="explicit_proxy" if proxy_list else "direct",
        run_id=None,
        identity_run_id=identity_run_id,
        proxy_list=proxy_list,
        proxy_profile=proxy_profile,
        locality_profile=locality_profile,
        selected_proxy=selected_proxy,
        selected_proxy_index=selected_proxy_index,
        browser_engine=browser_engine,
    )

async def _resolve_runtime_source(args: argparse.Namespace) -> RuntimeSource:
    explicit_proxies = list(args.proxy or [])
    if args.run_id is not None and (explicit_proxies or args.proxy_profile_json):
        raise ValueError("Provide either --run-id or explicit proxy flags, not both")
    if args.run_id is not None:
        return await _load_run_runtime_source(
            args.run_id, browser_engine=args.browser_engine
        )
    return _load_explicit_runtime_source(
        proxies=explicit_proxies,
        proxy_profile_path=args.proxy_profile_json,
        locality_profile=_coerce_locality_profile(
            geo_country=args.geo_country,
            language_hint=args.language_hint,
            currency_hint=args.currency_hint,
        ),
        browser_engine=args.browser_engine,
    )

def _masked_proxy_inventory(proxy_list: list[str]) -> list[str]:
    return [_display_proxy(value) for value in proxy_list]

def _report_root(base_dir: str | None) -> Path:
    base = (
        Path(base_dir)
        if base_dir
        else Path(__file__).resolve().parent / "artifacts" / _BUNDLE_DIRNAME
    )
    return base

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)
