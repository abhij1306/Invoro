from __future__ import annotations

__all__ = ("apply_dom_fallbacks",)

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.services.dom.html_parser import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser

from app.services.config.extraction_rules import DETAIL_DOM_SCALAR_SIZE_PATTERN
from app.services.dom.selector_engine import (
    apply_selector_fallbacks,
    extract_feature_rows,
    extract_heading_sections,
    extract_page_images,
)
from app.services.extract.detail.assembly import dom_section_targets as _section_targets
from app.services.extract.content_surface_extractor import (
    CONTENT_DETAIL_SURFACES,
    extract as extract_content_surface,
)
from app.services.extract.detail.price.inline_scalar import collect_inline_scalar_rows
from app.services.extract.detail.assembly.raw_signals import (
    breadcrumb_category_from_dom,
    gender_from_detail_context,
)
from app.services.shared.field_coerce import (
    RATING_RE,
    REVIEW_COUNT_RE,
    absolute_url,
    clean_text,
    coerce_field_value,
    extract_currency_code,
    is_title_noise,
    surface_alias_lookup,
    surface_fields,
    text_or_none,
)

_dom_section_target_fields = _section_targets._dom_section_target_fields


@dataclass
class _DomFallback:
    dom_parser: LexborHTMLParser
    soup: BeautifulSoup
    page_url: str
    surface: str
    requested_fields: list[str] | None
    candidates: dict[str, list[object]]
    candidate_sources: dict[str, list[str]]
    field_sources: dict[str, list[str]]
    selector_trace_candidates: dict[str, list[dict[str, object]]]
    selector_rules: list[dict[str, object]] | None
    add_sourced_candidate: Callable[..., None]
    breadcrumb_soup: BeautifulSoup | None

    def __post_init__(self) -> None:
        self.fields = surface_fields(self.surface, self.requested_fields)
        self.normalized_surface = str(self.surface or "").strip().lower()

    def add(self, field_name: str, value: object, *, source: str) -> None:
        self.add_sourced_candidate(
            self.candidates,
            self.candidate_sources,
            self.field_sources,
            field_name,
            value,
            source=source,
        )

    def add_content(self) -> bool:
        if self.normalized_surface not in CONTENT_DETAIL_SURFACES:
            return False
        values = extract_content_surface(
            self.soup, page_url=self.page_url, surface=self.normalized_surface
        )
        for field_name, value in values.items():
            if field_name in self.fields:
                self.add(
                    field_name,
                    coerce_field_value(field_name, value, self.page_url),
                    source="dom_text",
                )
        return True

    def add_title(self) -> str | None:
        has_h1 = self.soup.select_one("h1") is not None
        h1 = self.dom_parser.css_first("h1") if has_h1 else None
        page_title = self.dom_parser.css_first("title") if has_h1 else None
        h1_title = text_or_none(h1.text(separator=" ", strip=True) if h1 else "")
        page_title_text = text_or_none(
            page_title.text(separator=" ", strip=True) if page_title else ""
        )
        title = next(
            (
                value
                for value in (h1_title, page_title_text)
                if value and not is_title_noise(value)
            ),
            None,
        )
        if not title:
            return None
        before_count = len(self.candidates.get("title", []))
        self.add("title", title, source="dom_h1")
        if len(self.candidates.get("title", [])) > before_count:
            self._trace_title(title, "h1" if title == h1_title else "title")
        return title

    def _trace_title(self, title: str, selector_value: str) -> None:
        self.selector_trace_candidates.setdefault("title", []).append(
            {
                "selector_kind": "css_selector",
                "selector_value": selector_value,
                "selector_source": "dom_observed",
                "selector_record_id": None,
                "source_run_id": None,
                "sample_value": title,
                "page_url": self.page_url,
                "_candidate_value": title,
            }
        )

    def add_selector_fields(self) -> None:
        apply_selector_fallbacks(
            self.soup,
            self.page_url,
            self.surface,
            self.requested_fields,
            self.candidates,
            selector_rules=self.selector_rules,
            candidate_sources=self.candidate_sources,
            field_sources=self.field_sources,
            selector_trace_candidates=self.selector_trace_candidates,
            record_dom_observed_selectors=True,
        )

    def add_canonical_and_images(self) -> None:
        canonical = self.soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
        canonical_href = canonical.get("href") if canonical is not None else None
        if canonical_href:
            self.add(
                "url",
                absolute_url(self.page_url, canonical_href),
                source="dom_canonical",
            )
        images = extract_page_images(
            self.soup,
            self.page_url,
            exclude_linked_detail_images="detail" in self.normalized_surface,
            surface=self.surface,
        )
        if images:
            self.add("image_url", images[0], source="dom_images")
            self.add("additional_images", images[1:], source="dom_images")

    def add_inline_scalars(self, alias_lookup: dict[str, str]) -> None:
        targets: set[str] = {
            field
            for field in ("color", "size")
            if field in self.fields and not self.candidates.get(field)
        }
        for field_name, value in collect_inline_scalar_rows(
            self.soup, alias_lookup, allowed_fields=targets
        ):
            if field_name in self.fields and not self.candidates.get(field_name):
                self.add(
                    field_name,
                    coerce_field_value(field_name, value, self.page_url),
                    source="dom_text",
                )

    def add_sections(self, alias_lookup: dict[str, str]) -> None:
        section_fields = _dom_section_target_fields(self.surface, self.requested_fields)
        targets = {field for field in self.fields if field in section_fields}
        sections = extract_heading_sections(
            self.soup, alias_lookup=alias_lookup, allowed_fields=targets
        )
        for label, value in sections.items():
            normalized = alias_lookup.get(label.lower()) or alias_lookup.get(
                re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
            )
            if normalized:
                self.add(
                    normalized,
                    coerce_field_value(normalized, value, self.page_url),
                    source="dom_sections",
                )
        if "features" in self.fields and (
            feature_rows := extract_feature_rows(self.soup)
        ):
            self.add("features", feature_rows, source="dom_sections")

    def add_breadcrumb_fields(self, title: str | None) -> None:
        category = breadcrumb_category_from_dom(
            self.breadcrumb_soup or self.soup,
            current_title=title,
            page_url=self.page_url,
        )
        if "category" in self.fields and category:
            self.add("category", category, source="dom_breadcrumb")
        if "gender" not in self.fields or self.candidates.get("gender"):
            return
        gender = gender_from_detail_context(
            category, title, urlsplit(self.page_url).path
        )
        if gender:
            self.add("gender", gender, source="dom_text")

    def body_text(self) -> str:
        needed = any(
            (
                "size" in self.fields and not self.candidates.get("size"),
                "review_count" in self.fields
                and not self.candidates.get("review_count"),
                "rating" in self.fields and not self.candidates.get("rating"),
                self.normalized_surface.startswith("job_")
                and "remote" in self.fields
                and not self.candidates.get("remote"),
            )
        )
        body = self.dom_parser.body if needed else None
        return clean_text(body.text(separator=" ", strip=True)) if body else ""

    def add_body_scalars(self, body_text: str) -> None:
        self._add_pattern_scalar(
            "size", re.search(str(DETAIL_DOM_SCALAR_SIZE_PATTERN), body_text, re.I)
        )
        self._add_currency()
        self._add_pattern_scalar("review_count", REVIEW_COUNT_RE.search(body_text))
        self._add_pattern_scalar("rating", RATING_RE.search(body_text))
        if (
            self.normalized_surface.startswith("job_")
            and "remote" in self.fields
            and not self.candidates.get("remote")
            and any(term in body_text.lower() for term in ("remote", "work from home"))
        ):
            self.add("remote", "remote", source="dom_text")

    def _add_pattern_scalar(self, field_name: str, match: re.Match[str] | None) -> None:
        if field_name in self.fields and not self.candidates.get(field_name) and match:
            self.add(
                field_name,
                coerce_field_value(field_name, match.group(1), self.page_url),
                source="dom_text",
            )

    def _add_currency(self) -> None:
        if "currency" not in self.fields or self.candidates.get("currency"):
            return
        code = next(
            (
                currency
                for value in self.candidates.get("price") or []
                if (currency := extract_currency_code(value))
            ),
            None,
        )
        if code:
            self.add("currency", code, source="dom_text")


def apply_dom_fallbacks(
    dom_parser: LexborHTMLParser,
    soup: BeautifulSoup,
    *,
    page_url: str,
    surface: str,
    requested_fields: list[str] | None,
    candidates: dict[str, list[object]],
    candidate_sources: dict[str, list[str]],
    field_sources: dict[str, list[str]],
    selector_trace_candidates: dict[str, list[dict[str, object]]],
    selector_rules: list[dict[str, object]] | None,
    add_sourced_candidate: Callable[..., None],
    breadcrumb_soup: BeautifulSoup | None = None,
) -> None:
    fallback = _DomFallback(
        dom_parser=dom_parser,
        soup=soup,
        page_url=page_url,
        surface=surface,
        requested_fields=requested_fields,
        candidates=candidates,
        candidate_sources=candidate_sources,
        field_sources=field_sources,
        selector_trace_candidates=selector_trace_candidates,
        selector_rules=selector_rules,
        add_sourced_candidate=add_sourced_candidate,
        breadcrumb_soup=breadcrumb_soup,
    )
    if fallback.add_content():
        return
    # ``prune_irrelevant_detail_dom_nodes`` may decompose the body H1 on the
    # BeautifulSoup without touching the selectolax parser cache. Mirror that
    # decision here so the DOM fallback cannot resurrect a title from a page
    # whose primary structured evidence pointed to a different product.
    title = fallback.add_title()
    fallback.add_selector_fields()
    fallback.add_canonical_and_images()
    alias_lookup = surface_alias_lookup(surface, requested_fields)
    fallback.add_inline_scalars(alias_lookup)
    fallback.add_sections(alias_lookup)
    fallback.add_breadcrumb_fields(title)
    fallback.add_body_scalars(fallback.body_text())
