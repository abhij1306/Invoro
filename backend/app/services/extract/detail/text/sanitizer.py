from __future__ import annotations

from .long_text_sanitization import (document_link_label_patterns, fulfillment_only_long_text_phrases, fulfillment_long_text_patterns,
    guide_glossary_text_patterns, guide_glossary_heading_tokens, long_text_disclaimer_patterns, low_signal_title_values, low_signal_long_text_values,
    materials_pollution_tokens, low_signal_product_type_values, detail_artifact_product_type_patterns, cross_product_text_type_tokens,
    cross_product_text_generic_tokens, title_dimension_size_re, tracking_token_re, cookie_disclosure_text_patterns, low_signal_numeric_size_max,
    artifact_price_values, feature_row_noise_patterns, detail_title_value_is_low_signal, detail_product_type_is_low_signal,
    detail_scalar_size_is_low_signal, detail_candidate_is_valid, sanitize_detail_long_text_fields, sanitize_detail_long_text,
    sanitize_detail_features, detail_long_text_chunk_looks_truncated, detail_long_text_chunk_is_variant_size_sequence,
    detail_long_text_is_numeric_sequence, detail_long_text_is_fulfillment_only, detail_long_text_is_guide_or_glossary_dump,
    detail_long_text_is_cookie_disclosure_dump, detail_long_text_chunk_is_legal_tail, detail_long_text_chunk_is_document_label,
    detail_long_text_is_document_label_cluster, detail_long_text_chunk_is_variant_title, detail_long_text_chunk_is_other_product,
    detail_product_text_tokens, detail_long_text_chunk_has_product_name_shape, clean_materials_pollution,)

__all__ = ("document_link_label_patterns", "fulfillment_only_long_text_phrases", "fulfillment_long_text_patterns", "guide_glossary_text_patterns",
    "guide_glossary_heading_tokens", "long_text_disclaimer_patterns", "low_signal_title_values", "low_signal_long_text_values",
    "materials_pollution_tokens", "low_signal_product_type_values", "detail_artifact_product_type_patterns", "cross_product_text_type_tokens",
    "cross_product_text_generic_tokens", "title_dimension_size_re", "tracking_token_re", "cookie_disclosure_text_patterns",
    "low_signal_numeric_size_max", "artifact_price_values", "feature_row_noise_patterns", "detail_title_value_is_low_signal",
    "detail_product_type_is_low_signal", "detail_scalar_size_is_low_signal", "detail_candidate_is_valid", "sanitize_detail_long_text_fields",
    "sanitize_detail_long_text", "sanitize_detail_features", "detail_long_text_chunk_looks_truncated",
    "detail_long_text_chunk_is_variant_size_sequence", "detail_long_text_is_numeric_sequence", "detail_long_text_is_fulfillment_only",
    "detail_long_text_is_guide_or_glossary_dump", "detail_long_text_is_cookie_disclosure_dump", "detail_long_text_chunk_is_legal_tail",
    "detail_long_text_chunk_is_document_label", "detail_long_text_is_document_label_cluster", "detail_long_text_chunk_is_variant_title",
    "detail_long_text_chunk_is_other_product", "detail_product_text_tokens", "detail_long_text_chunk_has_product_name_shape",)


def _clean_materials_pollution(value: object) -> str:
    return clean_materials_pollution(value)
