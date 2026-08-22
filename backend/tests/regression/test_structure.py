from __future__ import annotations

import pytest

import ast
import importlib
import tomllib
from pathlib import Path

from radon.complexity import cc_visit

from app.core.database import Base

importlib.import_module("app.models")


ROOT = Path(__file__).resolve().parents[2]
SERVICES_ROOT = ROOT / "app" / "services"
APP_ROOT = ROOT / "app"
API_ROOT = APP_ROOT / "api"
TESTS_ROOT = ROOT / "tests"
REPO_ROOT = ROOT.parent
MAX_PHYSICAL_LINES = 800
MAX_CALLABLE_COMPLEXITY = 15
PYTHON_SCAN_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".cache",
        ".mypy_cache",
        ".pytest_cache",
        ".pytest-tmp",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "playwright-report",
        "test-results",
    }
)
EXTRACTION_MODULES = [
    SERVICES_ROOT / "extraction_context.py",
    SERVICES_ROOT / "listing_extractor.py",
    SERVICES_ROOT / "pipeline" / "extract_records.py",
    SERVICES_ROOT / "structured_sources.py",
    SERVICES_ROOT / "extract" / "field_candidates" / "structured_payloads.py",
    SERVICES_ROOT / "extract" / "field_candidates" / "structured_values.py",
    SERVICES_ROOT / "extract" / "field_candidates" / "variant_rows.py",
]
GENERIC_EXTRACTION_MODULES = []
FIELD_POLICY_CONSUMERS = [
    SERVICES_ROOT / "crawl" / "crud.py",
    SERVICES_ROOT / "schema_service.py",
    SERVICES_ROOT / "review" / "__init__.py",
]
ALLOWED_PRIVATE_SERVICE_IMPORTS = {
    # Existing relative private imports made visible by the audit ratchet.
    # Shrink this set when each owner promotes a real public API.
    "crawl/profile/acquisition_contract.py -> .normalization:_BROWSER_ENGINE_VALUES",
    "crawl/profile/acquisition_contract.py -> .normalization:_coerce_optional_choice",
    "crawl/profile/merge.py -> .normalization:_empty_acquisition_contract",
    "extract/field_candidates/structured_payloads.py -> .structured_values:_coerce_structured_candidate_value",
    "extract/field_candidates/structured_payloads.py -> .structured_values:_structured_alias_allowed",
    "extract/field_candidates/structured_payloads.py -> .structured_values:_structured_alias_value_allowed",
    "extract/field_candidates/structured_payloads.py -> .variant_rows:_structured_offer_variant_rows",
    "extract/field_candidates/structured_payloads.py -> .variant_rows:_structured_variant_rows",
    "extract/field_candidates/structured_payloads.py -> .variant_rows:_structured_variants_from_product_payload",
    "extract/field_candidates/structured_payloads.py -> .variant_rows:_variant_axes_from_rows",
    "extract/field_candidates/variant_rows.py -> .structured_values:_coerce_structured_candidate_value",
    "acquisition/traversal.py -> app.services.acquisition.traversal_recovery:_find_actionable_locator",
    # Package-private split modules behind stable public facades.
    "config/extraction_rules/__init__.py -> ._common:_STATIC_EXPORTS",
    "config/extraction_rules/__init__.py -> ._extra_exports:_EXTRA_EXPORTS",
    "config/extraction_rules/_detail.py -> ._common:_STATIC_EXPORTS",
    "config/extraction_rules/_images.py -> ._common:_BARE_HOST_URL_PATTERN",
    "config/extraction_rules/_images.py -> ._common:_CANDIDATE_IMAGE_FILE_EXTENSIONS",
    "config/extraction_rules/_images.py -> ._common:_STATIC_EXPORTS",
    "config/extraction_rules/_images.py -> ._common:_string_frozenset",
    "config/extraction_rules/_listing_structured.py -> ._common:_IMAGE_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_INTEGER_VALUE_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_LONG_TEXT_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_PRICE_VALUE_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_RATING_PATTERN",
    "config/extraction_rules/_listing_structured.py -> ._common:_REVIEW_COUNT_PATTERN",
    "config/extraction_rules/_listing_structured.py -> ._common:_REVIEW_TITLE_PATTERN",
    "config/extraction_rules/_listing_structured.py -> ._common:_SEMANTIC_SECTION_NOISE",
    "config/extraction_rules/_listing_structured.py -> ._common:_STATIC_EXPORTS",
    "config/extraction_rules/_listing_structured.py -> ._common:_STRUCTURED_MULTI_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_STRUCTURED_OBJECT_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_STRUCTURED_OBJECT_LIST_FIELDS_RAW",
    "config/extraction_rules/_listing_structured.py -> ._common:_URL_FIELDS_RAW",
    "js_state/state_normalizer/_facade.py -> ._identity:_mapped_product_family_matches",
    "js_state/state_normalizer/_facade.py -> ._identity:_mapped_product_identity_matches",
    "js_state/state_normalizer/_facade.py -> ._identity:_mapped_record_matches_page_url",
    "js_state/state_normalizer/_facade.py -> ._identity:_merge_same_product_record",
    "js_state/state_normalizer/_facade.py -> ._identity:_merge_variant_fields",
    "js_state/state_normalizer/_facade.py -> ._payloads:_find_product_payloads",
    "js_state/state_normalizer/_facade.py -> ._payloads:_looks_like_product_payload",
    "js_state/state_normalizer/_facade.py -> ._payloads:_normalized_state_payload",
    "js_state/state_normalizer/_facade.py -> ._product_mapping:_map_product_payload",
    "js_state/state_normalizer/_payloads.py -> ._variant_rows:_product_variant_rows",
    "js_state/state_normalizer/_product_mapping.py -> ._variant_mapping:_connection_nodes",
    "js_state/state_normalizer/_product_mapping.py -> ._variant_mapping:_name_or_value",
    "js_state/state_normalizer/_product_mapping.py -> ._variant_mapping:_normalize_variant",
    "js_state/state_normalizer/_product_mapping.py -> ._variant_mapping:_option_names",
    "js_state/state_normalizer/_product_mapping.py -> ._variant_rows:_product_variant_rows",
    "js_state/state_normalizer/_variant_rows.py -> ._variant_mapping:_option_names",
    "js_state/state_normalizer/_variant_rows.py -> ._variant_mapping:_variant_axis_raw_value",
}
ALLOWED_PRIVATE_TEST_IMPORTS: set[str] = {
    "tests/component/test_alert_service.py -> app.services.alert_service:_rules_payload",
    "tests/component/test_acquirer.py -> app.services.acquisition.internal_api_replay:_is_safe_replay_url",
    "tests/component/test_public_api.py -> app.main:_public_auth_session",
    "tests/component/test_public_api.py -> app.api.public.rate_limit:_retry_after",
    "tests/component/test_public_api.py -> app.api.public.rate_limit:_trim",
    "tests/component/test_sitemap_resolver.py -> app.services.crawl.sitemap_resolver:_normalize_sitemap_url",
    "tests/component/test_playground_service.py -> app.services.playground_service:_classify_input_url",
    "tests/component/test_playground_service.py -> app.services.playground_service:_merge_seed_detail_products",
    "tests/unit/test_content_article_forum_surfaces.py -> app.services.pipeline.retry.stage:_apply_detail_rejection_guard",
    "tests/unit/test_detail_image_cleanup.py -> app.services.extract.detail.images.cleanup:_detail_image_candidate_is_usable",
    "tests/unit/test_materials_sanitizer.py -> app.services.extract.detail.text.sanitizer:_clean_materials_pollution",
    "tests/component/test_public_api.py -> app.main:_crawler_app_state",
    "tests/regression/test_detail_extractor_structured_sources.py -> app.services.extract.field_candidates.variant_rows:_structured_variants_from_product_payload",
    "tests/regression/test_selectolax_css_migration.py -> app.services.extract.field_candidates.variant_rows:_structured_variants_from_product_payload",
    "tests/unit/test_normalizers.py -> app.services.extract.detail.assembly.final_cleanup:_reconcile_variant_derived_parent_fields",
}
ALLOWED_ROOT_EXTRACTION_MODULES = {
    # Slice 2 keeps this as the public listing orchestration facade.
    Path("app/services/listing_extractor.py"),
    # Canonical shared structured-source owner, explicitly out of this plan.
    Path("app/services/structured_sources.py"),
    # Shared extraction context types.
    Path("app/services/extraction_context.py"),
    # Generic script text extraction owner used by structured source parsing.
    Path("app/services/script_text_extractor.py"),
}
CONFIG_CONSTANT_NAME_MARKERS = (
    "SELECTOR",
    "TOKEN",
    "THRESHOLD",
    "TIMEOUT",
    "LIMIT",
    "RETRY",
    "PATH_MARKER",
)
ALLOWED_SERVICE_CONFIG_CONSTANTS = {
    ("acquisition/cookie_store.py", "_CHALLENGE_COOKIE_VALUE_TOKENS"),
    ("acquisition/cookie_store.py", "_CHALLENGE_LOCAL_STORAGE_NAME_TOKENS"),
    ("acquisition/cookie_store.py", "_CHALLENGE_LOCAL_STORAGE_VALUE_TOKENS"),
    ("acquisition/browser_readiness.py", "_ECOMMERCE_READY_CARD_SELECTORS"),
    ("dom/section_extraction.py", "_SECTION_CONTAINER_SELECTORS"),
    ("dom/section_extraction.py", "_SECTION_LABEL_SELECTOR"),
    ("shared/field_coerce.py", "_SIZE_REJECT_TOKENS_NORMALIZED"),
    ("normalizers/__init__.py", "_AVAILABILITY_TOKENS"),
    ("platform_policy.py", "_GENERIC_COMMERCE_TOKENS"),
    ("platform_policy.py", "_GENERIC_JOB_TOKENS"),
    ("playground_service.py", "SITEMAP_DISPLAY_LIMIT"),
}


@pytest.mark.regression
def test_detail_package_keeps_public_reexports() -> None:
    from app.services.extract import detail

    assert callable(detail.backfill_detail_price_from_html)
    assert callable(detail.repair_ecommerce_detail_record_quality)
    assert callable(detail.currency_hint_from_page_url)
    assert callable(detail.drop_low_signal_zero_detail_price)


@pytest.mark.regression
def test_variant_normalization_common_keeps_compatibility_reexports() -> None:
    from app.services.extract.variant_normalization import common
    from app.services.extract.variant_normalization.contract import (
        flatten_variants_for_public_output,
    )

    assert (
        common.flatten_variants_for_public_output is flatten_variants_for_public_output
    )


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _service_rel(path: Path) -> str:
    return path.relative_to(SERVICES_ROOT).as_posix()


def _module_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _module_all_names(path: Path) -> tuple[str, ...] | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        value_node = _module_all_value_node(node)
        if value_node is None:
            continue
        try:
            value = ast.literal_eval(value_node)
        except (TypeError, ValueError, SyntaxError):
            return None
        if not isinstance(value, (tuple, list)):
            return None
        if not all(isinstance(name, str) and name for name in value):
            return None
        return tuple(value)
    return None


def _module_all_value_node(node: ast.stmt) -> ast.AST | None:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "__all__"
        for target in node.targets
    ):
        return node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "__all__"
    ):
        return node.value
    return None


def _private_service_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    rel = _service_rel(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.module.startswith("app.services."):
            module_name = node.module
        elif node.level and node.module:
            module_name = "." * node.level + node.module
        else:
            continue
        for alias in node.names:
            if alias.name.startswith("_"):
                imports.add(f"{rel} -> {module_name}:{alias.name}")
    return imports


def _private_app_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    rel = path.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("app."):
            continue
        for alias in node.names:
            if alias.name.startswith("_"):
                imports.add(f"{rel} -> {node.module}:{alias.name}")
    return imports


def _maintained_python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if not set(path.relative_to(root).parts) & PYTHON_SCAN_EXCLUDED_DIRECTORIES
    )


def _physical_line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _callable_complexities(path: Path) -> list[tuple[str, int, int]]:
    blocks = cc_visit(path.read_text(encoding="utf-8"))
    callables: list[tuple[str, int, int]] = []
    pending = [block for block in blocks if block.letter in {"F", "M"}]
    while pending:
        block = pending.pop()
        callables.append((block.name, block.lineno, block.complexity))
        pending.extend(block.closures)
    return callables


@pytest.mark.regression
def test_maintained_python_files_meet_absolute_quality_limits() -> None:
    oversized: list[str] = []
    overcomplex: list[str] = []
    for path in _maintained_python_files(ROOT):
        relative_path = path.relative_to(ROOT).as_posix()
        line_count = _physical_line_count(path)
        if line_count > MAX_PHYSICAL_LINES:
            oversized.append(
                f"{relative_path} has {line_count} physical lines; "
                f"limit is {MAX_PHYSICAL_LINES}"
            )
        for name, line_number, complexity in _callable_complexities(path):
            if complexity > MAX_CALLABLE_COMPLEXITY:
                overcomplex.append(
                    f"{relative_path}:{line_number}:{name} has CC {complexity}; "
                    f"limit is {MAX_CALLABLE_COMPLEXITY}"
                )
    assert oversized == []
    assert overcomplex == []


@pytest.mark.regression
def test_absolute_quality_gate_boundaries(tmp_path: Path) -> None:
    exact_loc = tmp_path / "exact_loc.py"
    oversized = tmp_path / "oversized.py"
    exact_loc.write_text("pass\n" * MAX_PHYSICAL_LINES, encoding="utf-8")
    oversized.write_text("pass\n" * (MAX_PHYSICAL_LINES + 1), encoding="utf-8")
    assert _physical_line_count(exact_loc) == MAX_PHYSICAL_LINES
    assert _physical_line_count(oversized) == MAX_PHYSICAL_LINES + 1

    exact_cc = tmp_path / "exact_cc.py"
    overcomplex_cc = tmp_path / "overcomplex_cc.py"
    exact_cc.write_text(_synthetic_callable(MAX_CALLABLE_COMPLEXITY), encoding="utf-8")
    overcomplex_cc.write_text(
        _synthetic_callable(MAX_CALLABLE_COMPLEXITY + 1), encoding="utf-8"
    )
    assert _callable_complexities(exact_cc) == [
        ("synthetic", 1, MAX_CALLABLE_COMPLEXITY)
    ]
    assert _callable_complexities(overcomplex_cc) == [
        ("synthetic", 1, MAX_CALLABLE_COMPLEXITY + 1)
    ]


def _synthetic_callable(complexity: int) -> str:
    branches = [
        f"    if value == {index}:\n        return {index}\n"
        for index in range(complexity - 1)
    ]
    return "def synthetic(value):\n" + "".join(branches) + "    return -1\n"


@pytest.mark.regression
def test_python_quality_exclusions_are_narrow_and_explicit(tmp_path: Path) -> None:
    maintained = tmp_path / "app" / "maintained.py"
    maintained.parent.mkdir()
    maintained.write_text("pass\n", encoding="utf-8")
    for directory in PYTHON_SCAN_EXCLUDED_DIRECTORIES:
        excluded = tmp_path / directory / "ignored.py"
        excluded.parent.mkdir()
        excluded.write_text("pass\n" * (MAX_PHYSICAL_LINES + 1), encoding="utf-8")
    assert _maintained_python_files(tmp_path) == [maintained]


@pytest.mark.regression
def test_api_routes_do_not_own_session_factory() -> None:
    offenders: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "app.core.database":
                continue
            if any(alias.name == "SessionLocal" for alias in node.names):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.regression
def test_removed_architecture_audit_files_do_not_return() -> None:
    forbidden = [
        SERVICES_ROOT / "config" / "browser_init_scripts.py",
        SERVICES_ROOT / "pipeline" / "extraction_retry_stage.py",
    ]
    assert [str(path.relative_to(ROOT)) for path in forbidden if path.exists()] == []


@pytest.mark.regression
def test_root_extraction_services_are_explicitly_owned() -> None:
    root_extraction_modules = {
        path.relative_to(ROOT)
        for path in SERVICES_ROOT.glob("*.py")
        if path.name.endswith("_extractor.py")
        or path.name in {"extraction_context.py", "structured_sources.py"}
    }
    assert root_extraction_modules == ALLOWED_ROOT_EXTRACTION_MODULES


@pytest.mark.regression
def test_xpath_service_lives_under_dom_bucket() -> None:
    assert not (SERVICES_ROOT / "xpath_service.py").exists()
    assert (SERVICES_ROOT / "dom" / "xpath_service.py").exists()


@pytest.mark.regression
def test_extraction_modules_do_not_import_llm_runtime_layers() -> None:
    offenders: list[str] = []
    for path in EXTRACTION_MODULES:
        imports = _module_imports(path)
        if any(module.startswith("app.services.llm") for module in imports):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.regression
def test_generic_extraction_modules_do_not_import_site_adapters() -> None:
    offenders: list[str] = []
    for path in GENERIC_EXTRACTION_MODULES:
        imports = _module_imports(path)
        if any(module.startswith("app.services.adapters.") for module in imports):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.regression
def test_field_policy_is_the_only_field_rule_entrypoint() -> None:
    assert not (SERVICES_ROOT / "field_alias_policy.py").exists()
    assert not (SERVICES_ROOT / "requested_field_policy.py").exists()
    assert not (SERVICES_ROOT / "simple_crawler.py").exists()

    missing_imports: list[str] = []
    for path in FIELD_POLICY_CONSUMERS:
        imports = _module_imports(path)
        if "app.services.field_policy" not in imports:
            missing_imports.append(str(path.relative_to(ROOT)))
    assert missing_imports == []


@pytest.mark.regression
def test_new_config_like_modules_stay_under_services_config() -> None:
    offenders = [
        _service_rel(path)
        for path in SERVICES_ROOT.rglob("*.py")
        if "config" not in path.relative_to(SERVICES_ROOT).parts
        if path.name in {"config.py", "settings.py", "constants.py"}
        or path.name.endswith("_constants.py")
    ]
    assert offenders == []


@pytest.mark.regression
def test_root_binary_assets_are_not_committed_without_context() -> None:
    forbidden = [
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    ]
    assert forbidden == []
    logo_path = REPO_ROOT / "docs" / "assets" / "crawlerai-logo.png"
    if logo_path.parent.exists():
        assert logo_path.exists()


@pytest.mark.regression
def test_config_modules_do_not_mutate_globals_from_export_data() -> None:
    allowed_global_export_modules = {
        Path("app/services/config/extraction_rules/_listing_structured.py"),
        Path("app/services/config/extraction_rules/_variants.py"),
    }
    offenders: list[str] = []
    for path in (SERVICES_ROOT / "config").rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel in allowed_global_export_modules:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "globals":
                offenders.append(str(rel))
    assert sorted(offenders) == []


@pytest.mark.regression
def test_pylint_useful_checks_are_not_blanket_disabled() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    disabled = set(
        pyproject.get("tool", {})
        .get("pylint", {})
        .get("messages_control", {})
        .get("disable", [])
    )
    forbidden = {
        "duplicate-code",
        "missing-function-docstring",
        "too-many-arguments",
        "too-many-branches",
        "too-many-lines",
        "too-many-locals",
        "too-many-return-statements",
        "too-many-statements",
    }
    assert disabled & forbidden == set()


@pytest.mark.regression
def test_high_risk_services_do_not_use_broad_exception_catches() -> None:
    high_risk_paths = [
        SERVICES_ROOT / "alert_service.py",
        SERVICES_ROOT / "acquisition" / "traversal_helpers.py",
        SERVICES_ROOT / "acquisition" / "traversal_recovery.py",
        SERVICES_ROOT / "listing_extractor.py",
        SERVICES_ROOT / "llm" / "provider_client.py",
    ]
    offenders: list[str] = []
    for path in high_risk_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []


@pytest.mark.regression
def test_deleted_facades_do_not_return() -> None:
    def deleted_extract_module(*stem_parts: str) -> Path:
        return SERVICES_ROOT / "extract" / ("_".join(stem_parts) + ".py")

    stale_facades = [
        SERVICES_ROOT / "pipeline" / "core.py",
        deleted_extract_module("shared", "variant", "logic"),
        deleted_extract_module("variant", "grouping"),
        deleted_extract_module("detail", "materializer"),
        deleted_extract_module("detail", "dom", "extractor"),
        deleted_extract_module("detail", "dom", "context"),
        deleted_extract_module("detail", "record", "finalizer"),
        deleted_extract_module("detail", "identity"),
        deleted_extract_module("detail", "price", "extractor"),
    ]
    assert [
        str(path.relative_to(ROOT)) for path in stale_facades if path.exists()
    ] == []


@pytest.mark.regression
def test_extract_modules_declare_public_surface() -> None:
    missing: set[str] = set()
    for path in (SERVICES_ROOT / "extract").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        if "field_candidates" in path.relative_to(SERVICES_ROOT).parts:
            continue
        if not _module_all_names(path):
            missing.add(rel)
    assert missing == set()


@pytest.mark.regression
def test_flat_detail_modules_are_removed_after_decomposition() -> None:
    flat_detail_modules = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (SERVICES_ROOT / "extract").glob("detail_*.py")
    )
    assert flat_detail_modules == []


@pytest.mark.regression
def test_legacy_dispatcher_fallback_flag_is_removed() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if "legacy_inprocess_runner_enabled" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.regression
def test_retired_legacy_shims_do_not_return() -> None:
    forbidden = (
        "_LEGACY_PROMPTS_DIR",
        "_legacy_artifact_paths",
        "legacy_artifacts_removed",
        "legacy_keys",
        "legacy_aliases",
    )
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}:{token}")
    assert offenders == []


@pytest.mark.regression
def test_model_bootstrap_registers_domain_memory_tables() -> None:
    expected = {
        "domain_memory",
        "domain_run_profiles",
        "domain_cookie_memory",
        "domain_field_feedback",
        "host_protection_memory",
    }
    assert expected.issubset(Base.metadata.tables)


@pytest.mark.regression
def test_new_service_level_config_constants_are_not_added_outside_config() -> None:
    offenders: list[str] = []
    for path in SERVICES_ROOT.rglob("*.py"):
        rel_parts = path.relative_to(SERVICES_ROOT).parts
        if "config" in rel_parts:
            continue
        rel = _service_rel(path)
        for name in _module_level_names(path):
            if not name.isupper():
                continue
            if not any(marker in name for marker in CONFIG_CONSTANT_NAME_MARKERS):
                continue
            if (rel, name) not in ALLOWED_SERVICE_CONFIG_CONSTANTS:
                offenders.append(f"{rel}:{name}")
    assert sorted(offenders) == []


@pytest.mark.regression
def test_data_enrichment_taxonomy_matching_does_not_use_manual_category_alias_maps() -> (
    None
):
    config_text = (SERVICES_ROOT / "config" / "data_enrichment.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "DATA_ENRICHMENT_TAXONOMY_TOKEN_ALIASES",
        "DATA_ENRICHMENT_TAXONOMY_CONTEXTUAL_TOKEN_ALIASES",
    )
    assert [name for name in forbidden if name in config_text] == []


@pytest.mark.regression
def test_private_service_imports_do_not_drift() -> None:
    offenders: set[str] = set()
    for path in SERVICES_ROOT.rglob("*.py"):
        offenders.update(_private_service_imports(path))
    assert offenders == ALLOWED_PRIVATE_SERVICE_IMPORTS


@pytest.mark.regression
def test_private_test_imports_do_not_drift() -> None:
    offenders: set[str] = set()
    for path in TESTS_ROOT.rglob("*.py"):
        offenders.update(_private_app_imports(path))
    assert offenders == ALLOWED_PRIVATE_TEST_IMPORTS
