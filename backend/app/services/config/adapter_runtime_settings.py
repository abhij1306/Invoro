from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings

from app.services.config.runtime_settings import settings_config


class AdapterRuntimeSettings(BaseSettings):
    """Typed env-backed runtime settings for adapter-specific heuristics."""

    model_config = settings_config(env_prefix="ADAPTER_RUNTIME_")

    ats_request_timeout_seconds: int = 12
    shopify_request_timeout_seconds: int = 6
    shopify_catalog_limit: int = 250
    shopify_max_products: int = 500
    shopify_max_option_axis_count: int = 3
    shopify_linked_variant_max_handles: int = 8
    belk_max_products: int = 500
    belk_state_max_depth: int = 60
    icims_pagination_timeout_seconds: int = 15
    icims_page_size: int = 100
    icims_max_offset: int = 1000
    icims_title_min_length: int = 3
    bullhorn_page_size: int = 200
    bullhorn_max_offset: int = 1000
    bullhorn_request_timeout_seconds: int = 15
    default_locale: str = "en-US"
    jibe_listing_default_limit: str = "100"
    jibe_listing_default_page: str = "1"
    algolia_jobs_hits_per_page: int = 100
    firestore_jobs_page_size: int = 100
    oracle_hcm_detail_page_size: int = 25
    oracle_hcm_listing_page_size: int = 100
    paycom_listing_page_size: int = 100
    saashr_pagination_size: int = 50
    saashr_job_reqs_sort: str = "desc"

    @model_validator(mode="after")
    def _validate(self) -> AdapterRuntimeSettings:
        positive_fields = (
            "ats_request_timeout_seconds",
            "shopify_request_timeout_seconds",
            "shopify_catalog_limit",
            "shopify_max_products",
            "shopify_max_option_axis_count",
            "shopify_linked_variant_max_handles",
            "belk_max_products",
            "belk_state_max_depth",
            "icims_pagination_timeout_seconds",
            "icims_page_size",
            "icims_max_offset",
            "icims_title_min_length",
            "bullhorn_page_size",
            "bullhorn_max_offset",
            "bullhorn_request_timeout_seconds",
            "paycom_listing_page_size",
            "algolia_jobs_hits_per_page",
            "firestore_jobs_page_size",
            "oracle_hcm_detail_page_size",
            "oracle_hcm_listing_page_size",
            "saashr_pagination_size",
        )
        for field_name in positive_fields:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be > 0")
        if self.icims_max_offset < self.icims_page_size:
            raise ValueError("icims_max_offset must be >= icims_page_size")
        if self.bullhorn_max_offset < self.bullhorn_page_size:
            raise ValueError("bullhorn_max_offset must be >= bullhorn_page_size")
        if not str(self.saashr_job_reqs_sort or "").strip():
            raise ValueError("saashr_job_reqs_sort must not be empty")
        return self


adapter_runtime_settings = AdapterRuntimeSettings()

__all__ = ["AdapterRuntimeSettings", "adapter_runtime_settings"]
