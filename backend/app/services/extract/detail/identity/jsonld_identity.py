from __future__ import annotations

from bs4 import BeautifulSoup

__all__ = [
    "jsonld_item_candidate_record",
    "jsonld_item_product_name",
    "jsonld_item_supports_identity",
    "jsonld_items",
    "prune_duplicate_product_headings",
]


def _jsonld_graph_items(item: dict[str, object]) -> list[object]:
    graph = item.get("@graph")
    if isinstance(graph, list):
        return list(graph)
    if isinstance(graph, dict):
        return [graph]
    return [item]


def jsonld_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        items: list[object] = []
        for item in payload:
            items.extend(_jsonld_graph_items(item) if isinstance(item, dict) else [item])
        return items
    if isinstance(payload, dict):
        return _jsonld_graph_items(payload)
    return []


def jsonld_item_supports_identity(item: dict[str, object]) -> bool:
    return any(key in item for key in ("name", "offers", "sku", "mpn"))


def jsonld_item_product_name(item: dict[str, object]) -> str:
    raw_name = item.get("name")
    return raw_name.strip() if isinstance(raw_name, str) else ""


def jsonld_item_candidate_record(item: dict[str, object]) -> dict[str, object]:
    return {
        "title": item.get("name"),
        "sku": item.get("sku") or item.get("productId"),
        "brand": item.get("brand"),
        "color": item.get("color"),
        "size": item.get("size"),
        "description": item.get("description"),
    }


def prune_duplicate_product_headings(
    soup: BeautifulSoup,
    *,
    pruned_product_names: list[str],
) -> None:
    def _norm(value: str) -> str:
        return " ".join(value.lower().split())

    pruned_norms = {_norm(name) for name in pruned_product_names if name}
    h1_nodes = list(soup.find_all("h1"))
    keep_non_pruned_h1 = any(
        (h1_text := _norm(h1.get_text(separator=" ", strip=True)))
        and h1_text not in pruned_norms
        for h1 in h1_nodes
    )
    for h1 in h1_nodes:
        h1_text = _norm(h1.get_text(separator=" ", strip=True))
        if h1_text and h1_text in pruned_norms and keep_non_pruned_h1:
            h1.decompose()
