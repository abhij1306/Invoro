from __future__ import annotations

from ._support_shared import _ALLOWED_GENDERS_LOWER, _BARCODE_LENGTHS, _HIGH_DENOMINATION_PRICE_CURRENCIES, _INTERNAL_IDENTITY_TOKENS, _MIN_SANE_PRICE, _PUBLIC_RECORD_LEGACY_VARIANT_FIELDS, _VARIANT_AXIS_FIELDS  # fmt: skip
import re  # fmt: skip
from .challenge_classifier import _looks_like_detail_identity_mismatch, _looks_like_placeholder_or_wrong_content, _looks_like_promo_or_wrong_page, _looks_like_site_shell_success, _looks_like_utility_chrome_success  # fmt: skip
from .record_signals import _looks_like_real_listing_row, _looks_like_utility_record, _normalized_space, _object_dict, _object_list, _price_number, _safe_int  # fmt: skip


def evaluate_quality(
    site: dict[str, object],
    result: dict[str, object],
) -> dict[str, object]:
    expectations = _quality_expectations(site, result=result)
    checks = {
        "identity_ok": _quality_identity_ok(result),
        "listing_noise_ok": _quality_listing_noise_ok(
            result, expectations=expectations
        ),
        "variant_presence_ok": _quality_variant_presence_ok(
            result, expectations=expectations
        ),
        "variant_labels_ok": _quality_variant_labels_ok(
            result, expectations=expectations
        ),
        "variant_price_ok": _quality_variant_price_ok(
            result, expectations=expectations
        ),
        "price_sane_ok": _quality_price_sane_ok(result, expectations=expectations),
        "category_clean_ok": _quality_category_clean_ok(
            result, expectations=expectations
        ),
        "long_text_clean_ok": _quality_long_text_clean_ok(
            result, expectations=expectations
        ),
        "variant_artifacts_ok": _quality_variant_artifacts_ok(
            result, expectations=expectations
        ),
        "variant_currency_parity_ok": _quality_variant_currency_parity_ok(
            result, expectations=expectations
        ),
        "identifier_shapes_ok": _quality_identifier_shapes_ok(
            result, expectations=expectations
        ),
        "title_token_ok": _quality_title_token_ok(result, expectations=expectations),
        "system_artifacts_ok": _quality_system_artifacts_ok(
            result, expectations=expectations
        ),
        "repair_diagnostics_ok": _quality_repair_diagnostics_ok(
            result, expectations=expectations
        ),
    }
    observed_failure_mode = _observed_quality_failure_mode(
        site,
        result,
        checks=checks,
        expectations=expectations,
    )
    quality_verdict = _quality_verdict(
        result,
        checks=checks,
        expectations=expectations,
        observed_failure_mode=observed_failure_mode,
    )
    return {
        "quality_verdict": quality_verdict,
        "observed_failure_mode": observed_failure_mode,
        "quality_checks": checks,
    }


def _quality_expectations(
    site: dict[str, object],
    *,
    result: dict[str, object],
) -> dict[str, bool]:
    surface = str((site.get("surface") or result.get("surface") or "")).strip().lower()
    configured = _object_dict(site.get("quality_expectations"))
    expectations = {
        "require_identity": surface.endswith("_detail"),
        "require_listing_noise_free": surface.endswith("_listing"),
        "require_price": False,
        "require_price_sane": False,
        "require_clean_category": surface.startswith("ecommerce_"),
        "require_clean_long_text": surface == "ecommerce_detail",
        "require_clean_variants": surface == "ecommerce_detail",
        "require_clean_system_fields": surface == "ecommerce_detail",
        "require_identifier_shapes": surface == "ecommerce_detail",
        "require_title_not_internal_token": surface == "ecommerce_detail",
        "require_variant_currency_parity": surface == "ecommerce_detail",
        "require_repair_diagnostics": False,
        "expect_variants": False,
        "require_semantic_variant_labels": False,
        "require_variant_price": False,
    }
    for key in list(expectations):
        if key in configured:
            expectations[key] = bool(configured.get(key))
    return expectations


def _quality_identity_ok(result: dict[str, object]) -> bool:
    diagnostics = _object_dict(result.get("browser_diagnostics"))
    if str(result.get("failure_mode") or "").strip().lower() == "blocked":
        return False
    if _looks_like_placeholder_or_wrong_content(result, diagnostics):
        return False
    if _looks_like_detail_identity_mismatch(result):
        return False
    surface = str(result.get("surface") or "").strip().lower()
    if surface.endswith("_listing"):
        sample_records = _object_list(result.get("sample_records"))
        return any(
            isinstance(row, dict)
            and str(row.get("title") or "").strip()
            and str(row.get("url") or "").strip()
            and not _looks_like_utility_record(
                title=row.get("title"), url=row.get("url")
            )
            for row in sample_records
        )
    return not (
        _looks_like_site_shell_success(result)
        or _looks_like_promo_or_wrong_page(result)
    )


def _quality_listing_noise_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_listing_noise_free"):
        return True
    if _looks_like_utility_chrome_success(result):
        return False
    sample_records = _object_list(result.get("sample_records"))
    if sample_records and not any(
        _looks_like_real_listing_row(row) for row in sample_records[:3]
    ):
        return False
    return True


def _quality_variant_presence_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("expect_variants"):
        return True
    semantics = _object_dict(result.get("sample_semantics"))
    return _safe_int(semantics.get("variant_count")) >= 2


def _quality_variant_labels_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_semantic_variant_labels"):
        return True
    semantics = _object_dict(result.get("sample_semantics"))
    return bool(semantics.get("variants_all_have_axes"))


def _quality_variant_price_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_variant_price"):
        return True
    semantics = _object_dict(result.get("sample_semantics"))
    if bool(semantics.get("price_present")):
        return True
    return _safe_int(semantics.get("variants_with_price_count")) > 0


def _quality_price_sane_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_price_sane"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    price = _price_number(record.get("price"))
    if price is None or price < _MIN_SANE_PRICE:
        return False
    currency = str(record.get("currency") or "").strip().upper()
    max_price = 100000.0 if currency in _HIGH_DENOMINATION_PRICE_CURRENCIES else 10000.0
    return price <= max_price


def _quality_category_clean_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_clean_category"):
        return True
    category = str(_object_dict(result.get("sample_record_data")).get("category") or "")
    if not category.strip():
        return True
    lowered = f" {category.lower()} "
    if any(
        token in lowered
        for token in (
            " previous ",
            " next ",
            " view all ",
            " back ",
            " best sellers ",
            " shop by ",
            "···",
            " … ",
        )
    ):
        return False
    parts = [
        part.strip().lower() for part in re.split(r">\s*|/+", category) if part.strip()
    ]
    if any(
        part in {"home", "...", "all categories", "best sellers"}
        or part.startswith(("...", "shop by "))
        or part.endswith("...")
        for part in parts
    ):
        return False
    title = " ".join(str(result.get("sample_title") or "").strip().lower().split())
    sku = " ".join(
        str(_object_dict(result.get("sample_record_data")).get("sku") or "")
        .strip()
        .lower()
        .split()
    )
    return not bool(
        (title and any(part == title for part in parts))
        or (sku and any(part == sku or part.endswith(f"sku: {sku}") for part in parts))
    )


def _quality_long_text_clean_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_clean_long_text"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    description = _normalized_space(record.get("description"))
    specifications = _normalized_space(record.get("specifications"))
    if description and specifications and description == specifications:
        return False
    for field_name in (
        "description",
        "product_details",
        "specifications",
        "materials",
        "care",
    ):
        text = _normalized_space(record.get(field_name))
        lowered = text.lower()
        if not lowered:
            continue
        if (
            lowered.endswith((" show more", " more details"))
            or " learn more about our materials" in lowered
        ):
            return False
        if any(
            token in lowered
            for token in (
                "choose from same day delivery",
                "free standard delivery",
                "shipping and returns",
                "cookie policy",
                "privacy policy",
                "add to cart",
                "size guide",
                "view size guide",
                "ask a question",
                "we aim to show you accurate product information",
            )
        ):
            return False
        if re.search(r"\{['\"][a-z0-9_ -]+['\"]\s*:", text, flags=re.I):
            return False
        if field_name == "materials" and re.search(r"\breviews?\s*\(", lowered):
            return False
    return True


def _quality_variant_artifacts_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_clean_variants"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    if any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in _PUBLIC_RECORD_LEGACY_VARIANT_FIELDS
    ):
        return False
    values: list[object] = []
    allowed_variant_keys = {
        *_VARIANT_AXIS_FIELDS,
        "sku",
        "price",
        "currency",
        "url",
        "image_url",
        "availability",
        "stock_quantity",
    }
    for row in _object_list(record.get("variants")):
        if isinstance(row, dict):
            if any(str(key).strip() not in allowed_variant_keys for key in row.keys()):
                return False
            values.extend(row.keys())
            values.extend(row.values())
    for value in values:
        if isinstance(value, bool):
            return False
        text = _normalized_space(value).lower()
        if not text:
            continue
        if text in {"off", "on", "discount", "sale", "false", "true"}:
            return False
        if re.fullmatch(r"\d+\s*%", text) or re.fullmatch(
            # text has already been lowercased above via _normalized_space(...).lower()
            r"#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})",
            text,
        ):
            return False
    return True


def _quality_variant_currency_parity_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_variant_currency_parity"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    parent_currency = str(record.get("currency") or "").strip().upper()
    variants = [
        row for row in _object_list(record.get("variants")) if isinstance(row, dict)
    ]
    if not variants or not parent_currency:
        return True
    for row in variants:
        row_currency = str(row.get("currency") or "").strip().upper()
        if row_currency and row_currency != parent_currency:
            return False
        if row.get("price") not in (None, "", [], {}) and not row_currency:
            return False
    return True


def _quality_identifier_shapes_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_identifier_shapes"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    barcode = str(record.get("barcode") or "").strip()
    if barcode and (not barcode.isdigit() or len(barcode) not in _BARCODE_LENGTHS):
        return False
    gender = str(record.get("gender") or "").strip()
    if gender and gender.lower() not in _ALLOWED_GENDERS_LOWER:
        return False
    for field_name in ("product_id", "product_type"):
        text = str(record.get(field_name) or "").strip().lower()
        if text and any(token in text for token in _INTERNAL_IDENTITY_TOKENS):
            return False
    return True


def _quality_title_token_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_title_not_internal_token"):
        return True
    title = str(result.get("sample_title") or "").strip().lower()
    if not title:
        return True
    return title not in _INTERNAL_IDENTITY_TOKENS and "brightcove video" not in title


def _quality_system_artifacts_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_clean_system_fields"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    sku = str(record.get("sku") or "").strip().lower()
    product_type = str(record.get("product_type") or "").strip().lower()
    return not (sku.startswith("copy-") or product_type in {"default", "tag", "inline"})


def _quality_repair_diagnostics_ok(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_repair_diagnostics"):
        return True
    record = _object_dict(result.get("sample_record_data"))
    missing = [
        field_name
        for field_name in ("price", "title", "image_url")
        if record.get(field_name) in (None, "", [], {})
    ]
    if not missing:
        return True
    trace = _object_dict(result.get("sample_source_trace"))
    extraction = _object_dict(trace.get("extraction"))
    field_repair = _object_dict(
        extraction.get("field_repair") or trace.get("field_repair")
    )
    self_heal = _object_dict(extraction.get("self_heal") or trace.get("self_heal"))
    return bool(
        field_repair.get("reason")
        or field_repair.get("action")
        or self_heal.get("error")
        or bool(self_heal.get("triggered"))
    )


def _price_requirement_failed(
    result: dict[str, object],
    *,
    expectations: dict[str, bool],
) -> bool:
    if not expectations.get("require_price"):
        return False
    surface = str(result.get("surface") or "").strip().lower()
    if surface.endswith("_listing"):
        return not any(
            isinstance(row, dict) and bool(row.get("price_present"))
            for row in _object_list(result.get("sample_records"))
        )
    semantics = _object_dict(result.get("sample_semantics"))
    return not bool(semantics.get("price_present"))


def _observed_quality_failure_mode(
    site: dict[str, object],
    result: dict[str, object],
    *,
    checks: dict[str, bool],
    expectations: dict[str, bool],
) -> str:
    if str(result.get("failure_mode") or "").strip().lower() == "blocked":
        return "blocked"
    identity_failure = _identity_failure_mode(result, checks=checks)
    if identity_failure:
        return identity_failure
    if not checks["listing_noise_ok"]:
        return "listing_chrome_noise"
    requirement_failure = _requirement_failure_mode(
        checks=checks, expectations=expectations
    )
    if requirement_failure:
        return requirement_failure
    if _price_requirement_failed(result, expectations=expectations):
        return "thin_detail"
    seeded_failure_mode = str(site.get("seed_failure_mode") or "").strip().lower()
    if (
        str(result.get("run_source") or "").strip().lower() == "artifact_review"
        and seeded_failure_mode
    ):
        return seeded_failure_mode
    return "control_good"


def _identity_failure_mode(
    result: dict[str, object], *, checks: dict[str, bool]
) -> str | None:
    if checks["identity_ok"]:
        return None
    if _looks_like_promo_or_wrong_page(result):
        return "promo_or_wrong_page"
    if _looks_like_site_shell_success(result):
        return "shell_false_success"
    if _looks_like_detail_identity_mismatch(result):
        return "detail_identity_mismatch"
    return "bad_output"


def _requirement_failure_mode(
    *, checks: dict[str, bool], expectations: dict[str, bool]
) -> str | None:
    requirements = (
        ("expect_variants", "variant_presence_ok", "thin_detail"),
        ("require_semantic_variant_labels", "variant_labels_ok", "axis_pollution"),
        ("require_variant_price", "variant_price_ok", "variant_price_missing"),
        ("require_price_sane", "price_sane_ok", "price_magnitude_anomaly"),
        ("require_clean_category", "category_clean_ok", "category_pollution"),
        ("require_clean_long_text", "long_text_clean_ok", "long_text_pollution"),
        (
            "require_clean_variants",
            "variant_artifacts_ok",
            "variant_artifact_pollution",
        ),
        (
            "require_variant_currency_parity",
            "variant_currency_parity_ok",
            "variant_currency_mismatch",
        ),
        (
            "require_identifier_shapes",
            "identifier_shapes_ok",
            "identifier_shape_pollution",
        ),
        ("require_title_not_internal_token", "title_token_ok", "title_internal_token"),
        (
            "require_clean_system_fields",
            "system_artifacts_ok",
            "system_artifact_pollution",
        ),
        (
            "require_repair_diagnostics",
            "repair_diagnostics_ok",
            "repair_diagnostic_missing",
        ),
    )
    for expectation, check, failure_mode in requirements:
        if expectations.get(expectation) and not checks[check]:
            return failure_mode
    return None


def _quality_verdict(
    result: dict[str, object],
    *,
    checks: dict[str, bool],
    expectations: dict[str, bool],
    observed_failure_mode: str,
) -> str:
    if str(result.get("failure_mode") or "").strip().lower() == "blocked":
        return "blocked"
    if observed_failure_mode in {
        "bad_output",
        "detail_identity_mismatch",
        "listing_chrome_noise",
        "promo_or_wrong_page",
        "shell_false_success",
        "price_magnitude_anomaly",
        "category_pollution",
        "long_text_pollution",
        "variant_artifact_pollution",
        "variant_currency_mismatch",
        "identifier_shape_pollution",
        "title_internal_token",
        "system_artifact_pollution",
        "repair_diagnostic_missing",
    }:
        return "bad_output"
    if _price_requirement_failed(result, expectations=expectations):
        return "usable_with_gaps"
    if not all(bool(value) for value in checks.values()):
        return "usable_with_gaps"
    return "good"


__all__ = ['_ALLOWED_GENDERS_LOWER', '_BARCODE_LENGTHS', '_HIGH_DENOMINATION_PRICE_CURRENCIES', '_INTERNAL_IDENTITY_TOKENS', '_MIN_SANE_PRICE', '_PUBLIC_RECORD_LEGACY_VARIANT_FIELDS', '_VARIANT_AXIS_FIELDS', '_identity_failure_mode', '_looks_like_detail_identity_mismatch', '_looks_like_placeholder_or_wrong_content', '_looks_like_promo_or_wrong_page', '_looks_like_real_listing_row', '_looks_like_site_shell_success', '_looks_like_utility_chrome_success', '_looks_like_utility_record', '_normalized_space', '_object_dict', '_object_list', '_observed_quality_failure_mode', '_price_number', '_price_requirement_failed', '_quality_category_clean_ok', '_quality_expectations', '_quality_identifier_shapes_ok', '_quality_identity_ok', '_quality_listing_noise_ok', '_quality_long_text_clean_ok', '_quality_price_sane_ok', '_quality_repair_diagnostics_ok', '_quality_system_artifacts_ok', '_quality_title_token_ok', '_quality_variant_artifacts_ok', '_quality_variant_currency_parity_ok', '_quality_variant_labels_ok', '_quality_variant_presence_ok', '_quality_variant_price_ok', '_quality_verdict', '_requirement_failure_mode', '_safe_int', 'annotations', 'evaluate_quality', 're']  # fmt: skip
