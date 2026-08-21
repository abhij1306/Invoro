# ruff: noqa: F401, F821
from __future__ import annotations

from . import selector_engine as _owner

globals().update({name: value for name, value in vars(_owner).items() if not name.startswith("__")})

def _different_detail_link_signal(
    raw_path: str,
    surface: str | None,
    is_detail_surface: bool,
    same_host: bool,
    same_path: bool,
    link_node: Tag | None,
) -> bool:
    path = raw_path.lower()
    if any(path.endswith(ext) for ext in _PAGE_FILE_EXTENSIONS):
        return True
    if any(marker in path for marker in detail_path_hints(surface)):
        return True
    if is_detail_surface and same_host and not same_path:
        return True
    return link_node is not None and _is_in_cross_link_container(link_node)

def _is_in_cross_link_container(node: Tag, *, max_depth: int = 6) -> bool:
    return (
        walk_ancestors(
            node,
            lambda current, _depth: any(hint in _node_attr_text(current) for hint in CROSS_LINK_CONTAINER_HINTS),
            max_depth=max_depth,
        )
        is not None
    )

def extract_node_value(node: Tag, field_name: str, page_url: str) -> object | None:
    if field_name in IMAGE_FIELDS:
        return _image_node_value(node, field_name, page_url)
    if field_name in URL_FIELDS:
        urls = extract_urls(
            node.get("href") or node.get("content") or node.get("data-apply-url") or "",
            page_url,
        )
        return urls[0] if urls else None
    has_attr_value, attr_value = _node_scalar_attribute(node)
    if has_attr_value:
        return coerce_field_value(field_name, attr_value, page_url)
    raw_text = _node_raw_text(node, field_name)
    text_value = coerce_field_value(field_name, raw_text, page_url)
    if field_name in LONG_TEXT_FIELDS and not section_text_is_meaningful(
        node,
        label=field_name,
        text=str(text_value or ""),
    ):
        return None
    return text_value

def _image_node_value(node: Tag, field_name: str, page_url: str) -> object | None:
    srcset = node.get("srcset")
    image_candidates: object = srcset_urls(srcset) if srcset not in (None, "", [], {}) else _fallback_image_candidate(node)
    urls = extract_urls(image_candidates, page_url)
    if node.name not in {"img", "source"} and str(node.get("as") or "").lower() != "image":
        urls = [url for url in urls if looks_like_image_asset_url(url)]
    if field_name == ADDITIONAL_IMAGES_FIELD:
        return urls or None
    return urls[0] if urls else None

def _fallback_image_candidate(node: Tag) -> object:
    return (
        node.get("content")
        or next(
            (node.get(str(attr_name)) for attr_name in tuple(DETAIL_IMAGE_URL_ATTRS or ()) if node.get(str(attr_name)) not in (None, "", [], {})),
            None,
        )
        or node.get("href")
        or ""
    )

def _node_scalar_attribute(node: Tag) -> tuple[bool, object | None]:
    if node.name == "meta":
        return True, node.get("content")
    for attr_name in (
        "content",
        "value",
        "datetime",
        "data-value",
        "data-price",
        "data-availability",
    ):
        value = node.get(attr_name)
        if value not in (None, "", [], {}):
            return True, value
    return False, None

def _node_raw_text(node: Tag, field_name: str) -> str:
    if _looks_like_variant_option_node(node, field_name):
        return _variant_option_node_text(node, field_name)
    visible = cast(Tag, _clone_visible_only(node) or node)
    if _field_uses_scoped_text(field_name):
        return html_to_text(str(visible), preserve_block_breaks=True)
    return visible.get_text(" ", strip=True)

def _looks_like_variant_option_node(node: Tag, field_name: str) -> bool:
    if field_name not in VARIANT_OPTION_TEXT_FIELDS:
        return False
    if node.name in {"option", "button"}:
        return True
    role = str(node.get("role") or "").strip().lower()
    if role in {"option", "radio", "button", "tab"}:
        return True
    context = " ".join(
        _attribute_text(value)
        for value in (
            node.get("class"),
            node.get("aria-label"),
            node.get("data-testid"),
            node.get("data-test"),
            node.get("data-qa"),
            node.get("name"),
        )
    ).lower()
    return any(token in context for token in ("option", "swatch", "variant", field_name))

def _attribute_text(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item or "") for item in value)
    return str(value or "")

def _variant_option_node_text(node: Tag, _field_name: str) -> str:
    if not node.find(True):
        return node.get_text(" ", strip=True)
    kept: list[str] = []
    for child in node.contents:
        if isinstance(child, NavigableString):
            text = clean_text(str(child))
        elif isinstance(child, Tag):
            text = clean_text(child.get_text(" ", strip=True))
        else:
            continue
        if not text:
            continue
        if any(pattern.search(text) for pattern in _VARIANT_OPTION_CHILD_DROP_RE):
            continue
        kept.append(text)
    return " ".join(kept)

def extract_selector_values(
    root: BeautifulSoup | Tag,
    selector: str,
    field_name: str,
    page_url: str,
) -> list[object]:
    values: list[object] = []
    scoped_text_root = _best_text_scope(root) if _field_uses_scoped_text(field_name) else None
    for node in safe_select(root, selector)[:_max_selector_matches]:
        if _field_uses_scoped_text(field_name):
            if _node_is_hidden_or_auxiliary(node):
                continue
            if scoped_text_root is not None and not _node_within_scope(node, scoped_text_root):
                continue
        value = extract_node_value(node, field_name, page_url)
        if value in (None, "", [], {}):
            continue
        values.append(value)
    return values

def extract_xpath_values(
    root: BeautifulSoup | Tag,
    xpath: str,
    field_name: str,
    page_url: str,
) -> list[object]:
    valid_xpath, _ = validate_xpath_syntax(xpath)
    if not valid_xpath:
        logger.warning("Skipping invalid xpath selector for %s: %s", field_name, xpath)
        return []
    try:
        tree = lxml_html.fromstring(str(root))
    except (etree.ParserError, ValueError):
        return []
    try:
        matches = tree.xpath(xpath)
    except etree.XPathError:
        logger.warning("Failed to evaluate xpath selector for %s: %s", field_name, xpath)
        return []
    values: list[object] = []
    limited_matches: list[object]
    if isinstance(matches, list):
        limited_matches = [*matches[:_max_selector_matches]]
    elif isinstance(matches, (str, bytes, bool, float)):
        limited_matches = [matches]
    else:
        try:
            limited_matches = list(matches)[:_max_selector_matches]
        except TypeError:
            limited_matches = [matches]
    for match in limited_matches:
        if isinstance(match, lxml_html.HtmlElement):
            raw_value = match.text_content()
        elif isinstance(match, etree._Element):
            raw_value = " ".join(str(part) for part in match.itertext())
        else:
            raw_value = str(match)
        value = coerce_field_value(field_name, raw_value, page_url)
        if value in (None, "", [], {}):
            continue
        values.append(value)
    return values

def extract_regex_values(
    root: BeautifulSoup | Tag,
    pattern: str,
    field_name: str,
    page_url: str,
) -> list[object]:
    html_text = str(root)
    values: list[object] = []
    timeout = _selector_regex_timeout_seconds()
    try:
        matches = regex_lib.finditer(
            pattern,
            html_text,
            regex_lib.DOTALL,
            timeout=timeout,
        )
        for match in matches:
            raw_value = next((group for group in match.groups() if group), None)
            if raw_value is None:
                raw_value = match.group(0)
            value = coerce_field_value(field_name, raw_value, page_url)
            if value in (None, "", [], {}):
                continue
            values.append(value)
            if len(values) >= 12:
                break
    except TimeoutError:
        logger.warning("Timed out while evaluating selector regex for %s", field_name)
    except regex_lib.error:
        logger.warning("Failed to evaluate selector regex for %s", field_name)
    return values

def filter_values_by_regex(
    values: list[object],
    pattern: str,
    field_name: str,
    page_url: str,
) -> list[object]:
    filtered: list[object] = []
    timeout = _selector_regex_timeout_seconds()
    try:
        for candidate in values:
            match = regex_lib.search(
                pattern,
                str(candidate),
                regex_lib.DOTALL,
                timeout=timeout,
            )
            if not match:
                continue
            raw_value = next((group for group in match.groups() if group), None)
            if raw_value is None:
                raw_value = match.group(0)
            value = coerce_field_value(field_name, raw_value, page_url)
            if value in (None, "", [], {}):
                continue
            filtered.append(value)
            if len(filtered) >= 12:
                break
    except TimeoutError:
        logger.warning("Timed out while evaluating selector regex for %s", field_name)
    except regex_lib.error:
        logger.warning("Failed to evaluate selector regex for %s", field_name)
    return filtered

def extract_page_images(
    root: BeautifulSoup | Tag,
    page_url: str,
    *,
    exclude_linked_detail_images: bool = False,
    surface: str | None = None,
) -> list[str]:
    return extract_page_images_impl(
        root,
        page_url,
        exclude_linked_detail_images=exclude_linked_detail_images,
        surface=surface,
        other_detail_link_checker=_is_other_detail_link,
    )

def requested_content_extractability(
    root: BeautifulSoup | Tag,
    *,
    surface: str,
    requested_fields: list[str] | None,
    selector_rules: list[dict[str, object]] | None = None,
    probe_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, object]:
    return requested_content_extractability_impl(
        root,
        surface=surface,
        requested_fields=requested_fields,
        selector_rules=selector_rules,
        probe_fields=probe_fields,
        extract_heading_sections=extract_heading_sections,  # type: ignore[arg-type]
        safe_select=safe_select,
        max_selector_matches=_max_selector_matches,
    )

def apply_selector_fallbacks(
    root: BeautifulSoup | Tag,
    page_url: str,
    surface: str,
    requested_fields: list[str] | None,
    candidates: dict[str, list[object]],
    selector_rules: list[dict[str, object]] | None = None,
    *,
    candidate_sources: dict[str, list[str]] | None = None,
    field_sources: dict[str, list[str]] | None = None,
    selector_trace_candidates: dict[str, list[dict[str, object]]] | None = None,
    record_dom_observed_selectors: bool = False,
) -> None:
    def _add(field_name: str, value: object, source: str) -> int:
        growth = add_candidate(candidates, field_name, value)
        if growth <= 0:
            return 0
        if candidate_sources is not None:
            candidate_sources.setdefault(field_name, []).extend([source] * growth)
        if field_sources is not None:
            bucket = field_sources.setdefault(field_name, [])
            public_source = "dom_selector" if source == "selector_rule" else source
            if public_source not in bucket:
                bucket.append(public_source)
        return growth

    def _record_selector_trace(
        field_name: str,
        value: object,
        row: dict[str, object],
        *,
        selector_kind: str,
        selector_value: str,
    ) -> None:
        if selector_trace_candidates is None:
            return
        selector_trace_candidates.setdefault(field_name, []).append(
            {
                "selector_kind": selector_kind,
                "selector_value": selector_value,
                "selector_source": str(row.get("source") or "domain_memory").strip(),
                "selector_record_id": row.get("id"),
                "source_run_id": row.get("source_run_id"),
                "sample_value": str(value),
                "page_url": page_url,
                "_candidate_value": value,
            }
        )

    fields = surface_fields(surface, requested_fields)
    alias_lookup = surface_alias_lookup(surface, requested_fields)
    selector_hit_fields = _apply_selector_rules(root, page_url, fields, selector_rules, _add, _record_selector_trace)
    _apply_dom_patterns(
        root,
        page_url,
        fields,
        selector_hit_fields,
        _add,
        _record_selector_trace,
        record_dom_observed_selectors,
    )
    _apply_label_pairs(root, page_url, alias_lookup, _add)

def _apply_selector_rules(
    root: BeautifulSoup | Tag,
    page_url: str,
    fields: list[str],
    selector_rules: list[dict[str, object]] | None,
    add: Callable[[str, object, str], int],
    record_trace: Callable[..., None],
) -> set[str]:
    hit_fields: set[str] = set()
    for row in list(selector_rules or []):
        if not isinstance(row, dict):
            continue
        field_name = normalize_field_key(str(row.get("field_name") or ""))
        if field_name not in fields or not bool(row.get("is_active", True)):
            continue
        xpath = str(row.get("xpath") or "").strip()
        css_selector = str(row.get("css_selector") or "").strip()
        regex = str(row.get("regex") or "").strip()
        values, selector_kind, selector_value = _selector_rule_values(root, page_url, field_name, xpath, css_selector, regex)
        for value in values:
            if add(field_name, value, "selector_rule") > 0 and selector_kind and selector_value:
                record_trace(
                    field_name,
                    value,
                    row,
                    selector_kind=selector_kind,
                    selector_value=selector_value,
                )
        if values:
            hit_fields.add(field_name)
    return hit_fields

def _selector_rule_values(
    root: BeautifulSoup | Tag,
    page_url: str,
    field_name: str,
    xpath: str,
    css_selector: str,
    regex: str,
) -> tuple[list[object], str, str]:
    values: list[object] = []
    selector_kind = ""
    selector_value = ""
    if xpath:
        values = extract_xpath_values(root, xpath, field_name, page_url)
        selector_kind, selector_value = "xpath", xpath
    if not values and css_selector:
        values = extract_selector_values(root, css_selector, field_name, page_url)
        selector_kind, selector_value = "css_selector", css_selector
    if values and regex:
        values = filter_values_by_regex(values, regex, field_name, page_url)
    elif not values and regex and not xpath and not css_selector:
        values = extract_regex_values(root, regex, field_name, page_url)
        selector_kind, selector_value = "regex", regex
    return values, selector_kind, selector_value

def _apply_dom_patterns(
    root: BeautifulSoup | Tag,
    page_url: str,
    fields: list[str],
    selector_hit_fields: set[str],
    add: Callable[[str, object, str], int],
    record_trace: Callable[..., None],
    record_dom_observed_selectors: bool,
) -> None:
    dom_patterns_raw = EXTRACTION_RULES.get("dom_patterns")
    dom_patterns = dict(dom_patterns_raw) if isinstance(dom_patterns_raw, dict) else {}
    for field_name in fields:
        if field_name in selector_hit_fields:
            continue
        selector = str(dom_patterns.get(field_name) or "").strip()
        if not selector:
            continue
        for value in extract_selector_values(root, selector, field_name, page_url):
            if add(field_name, value, "dom_selector") > 0 and record_dom_observed_selectors:
                record_trace(
                    field_name,
                    value,
                    {"source": "dom_observed"},
                    selector_kind="css_selector",
                    selector_value=selector,
                )

def _apply_label_pairs(
    root: BeautifulSoup | Tag,
    page_url: str,
    alias_lookup: dict[str, str],
    add: Callable[[str, object, str], int],
) -> None:
    for label, value in extract_label_value_pairs(root):
        normalized_label = normalize_field_key(label)
        canonical = alias_lookup.get(normalized_label)
        if not canonical:
            canonical = alias_lookup.get(normalize_requested_field(label))
        if canonical:
            add(
                canonical,
                coerce_field_value(canonical, value, page_url),
                "dom_selector",
            )
