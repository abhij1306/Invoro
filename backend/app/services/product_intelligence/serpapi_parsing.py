from __future__ import annotations

from app.services.config.product_intelligence import (
    SEARCH_PROVIDER_SERPAPI,
    SERPAPI_LINK_FIELD,
    SERPAPI_ORGANIC_RESULTS_FIELD,
    SERPAPI_POSITION_FIELD,
    SERPAPI_SHOPPING_IMMERSIVE_API_FIELD,
    SERPAPI_SHOPPING_LINK_FIELDS,
    SERPAPI_SHOPPING_PRODUCT_ID_FIELD,
    SERPAPI_SHOPPING_PRODUCT_LINK_FIELD,
    SERPAPI_SHOPPING_RESULTS_FIELD,
    SERPAPI_SNIPPET_FIELD,
    SERPAPI_SOURCE_FIELD,
    SERPAPI_TITLE_FIELD,
)
from app.services.product_intelligence.candidate_urls import clean_result_url
from app.services.product_intelligence.search_types import SearchResult


def parse_organic_results(payload: dict[str, object]) -> list[SearchResult]:
    rows = payload.get(SERPAPI_ORGANIC_RESULTS_FIELD)
    if not isinstance(rows, list):
        return []
    return [
        SearchResult(
            url=str(item.get(SERPAPI_LINK_FIELD) or ""),
            payload={
                "provider": SEARCH_PROVIDER_SERPAPI,
                "title": str(item.get(SERPAPI_TITLE_FIELD) or ""),
                "snippet": str(item.get(SERPAPI_SNIPPET_FIELD) or ""),
                "position": item.get(SERPAPI_POSITION_FIELD),
                "raw": item,
            },
        )
        for item in rows
        if isinstance(item, dict) and item.get(SERPAPI_LINK_FIELD)
    ]


def parse_shopping_results(payload: dict[str, object]) -> list[SearchResult]:
    rows = payload.get(SERPAPI_SHOPPING_RESULTS_FIELD)
    if not isinstance(rows, list):
        return []
    results: list[SearchResult] = []
    for item in rows:
        if isinstance(item, dict) and (url := first_shopping_url(item)):
            results.append(SearchResult(url=url, payload=_shopping_payload(item)))
    return results


def _shopping_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "provider": "serpapi_shopping",
        "title": str(item.get(SERPAPI_TITLE_FIELD) or ""),
        "snippet": str(item.get("snippet") or item.get("extensions") or ""),
        "source": str(item.get(SERPAPI_SOURCE_FIELD) or ""),
        "price": item.get("price"),
        "extracted_price": item.get("extracted_price"),
        "thumbnail": str(item.get("thumbnail") or ""),
        "position": item.get(SERPAPI_POSITION_FIELD),
        "product_id": item.get(SERPAPI_SHOPPING_PRODUCT_ID_FIELD),
        "product_link": item.get(SERPAPI_SHOPPING_PRODUCT_LINK_FIELD),
        "serpapi_immersive_product_api": item.get(SERPAPI_SHOPPING_IMMERSIVE_API_FIELD),
        "rating": item.get("rating"),
        "reviews": item.get("reviews"),
        "delivery": item.get("delivery"),
        "raw": item,
    }


def parse_immersive_results(
    payload: dict[str, object],
    *,
    parent: dict[str, object] | None = None,
    limit: int | None = None,
) -> list[SearchResult]:
    parent_data = parent or {}
    product_value = payload.get("product_results")
    product = product_value if isinstance(product_value, dict) else {}
    thumbnail = _first_thumbnail(product)
    results = _store_results(
        product, parent_data=parent_data, thumbnail=thumbnail, limit=limit
    )
    result_limit = max(1, int(limit)) if limit is not None else None
    if result_limit is not None and len(results) >= result_limit:
        return results[:result_limit]
    if about_result := _about_product_result(
        product, parent_data=parent_data, thumbnail=thumbnail, position=len(results) + 1
    ):
        results.append(about_result)
    return results


def _store_results(
    product: dict[str, object],
    *,
    parent_data: dict[str, object],
    thumbnail: str,
    limit: int | None,
) -> list[SearchResult]:
    stores = product.get("stores")
    store_rows = stores if isinstance(stores, list) else []
    result_limit = max(1, int(limit)) if limit is not None else None
    pruned_product = _pruned_product(product)
    results: list[SearchResult] = []
    for position, store in enumerate(store_rows, start=1):
        if not isinstance(store, dict) or not (
            url := clean_result_url(store.get("link"))
        ):
            continue
        results.append(
            SearchResult(
                url=url,
                payload=_store_payload(
                    store,
                    product=product,
                    parent_data=parent_data,
                    pruned_product=pruned_product,
                    thumbnail=thumbnail,
                    position=position,
                ),
            )
        )
        if result_limit is not None and len(results) >= result_limit:
            break
    return results


def _store_payload(
    store: dict[str, object],
    *,
    product: dict[str, object],
    parent_data: dict[str, object],
    pruned_product: dict[str, object],
    thumbnail: str,
    position: int,
) -> dict[str, object]:
    return {
        "provider": "serpapi_immersive",
        "title": str(
            store.get("title") or product.get("title") or parent_data.get("title") or ""
        ),
        "snippet": str(product.get("description") or ""),
        "source": str(store.get("name") or ""),
        "price": store.get("price"),
        "extracted_price": store.get("extracted_price"),
        "thumbnail": thumbnail,
        "position": position,
        "product_id": product.get("product_id")
        or parent_data.get(SERPAPI_SHOPPING_PRODUCT_ID_FIELD),
        "product_link": parent_data.get(SERPAPI_SHOPPING_PRODUCT_LINK_FIELD),
        "rating": store.get("rating") or product.get("rating"),
        "reviews": store.get("reviews") or product.get("reviews"),
        "delivery": store.get("shipping") or "",
        "raw": {"store": store, "product": pruned_product, "parent": parent_data},
    }


def _about_product_result(
    product: dict[str, object],
    *,
    parent_data: dict[str, object],
    thumbnail: str,
    position: int,
) -> SearchResult | None:
    about = product.get("about_the_product")
    if not isinstance(about, dict) or not (url := clean_result_url(about.get("link"))):
        return None
    return SearchResult(
        url=url,
        payload={
            "provider": "serpapi_immersive",
            "title": str(about.get("title") or product.get("title") or ""),
            "snippet": str(about.get("description") or ""),
            "source": str(about.get("displayed_link") or ""),
            "thumbnail": thumbnail,
            "position": position,
            "product_id": product.get("product_id")
            or parent_data.get(SERPAPI_SHOPPING_PRODUCT_ID_FIELD),
            "product_link": parent_data.get(SERPAPI_SHOPPING_PRODUCT_LINK_FIELD),
            "raw": {
                "about_the_product": about,
                "product": _pruned_product(product),
                "parent": parent_data,
            },
        },
    )


def _pruned_product(product: dict[str, object]) -> dict[str, object]:
    about = product.get("about_the_product")
    about_data = about if isinstance(about, dict) else {}
    return {
        "title": product.get("title"),
        "brand": product.get("brand"),
        "rating": product.get("rating"),
        "reviews": product.get("reviews"),
        "description": product.get("description")
        or about_data.get("description")
        or "",
    }


def _first_thumbnail(product: dict[str, object]) -> str:
    thumbnails = product.get("thumbnails")
    return (
        str(thumbnails[0] or "") if isinstance(thumbnails, list) and thumbnails else ""
    )


def first_shopping_url(item: dict[str, object]) -> str:
    for field in SERPAPI_SHOPPING_LINK_FIELDS:
        if item.get(field) and (cleaned := clean_result_url(item[field])):
            return cleaned
    return ""


def dedupe_search_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for result in results:
        cleaned = clean_result_url(result.url)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(SearchResult(url=cleaned, payload=result.payload))
    return deduped
