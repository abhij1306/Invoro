from __future__ import annotations

import re

from app.services.shared.field_coerce import clean_text, strip_html_tags

token_re = re.compile(r"[a-z0-9]+")


def normalize_category_path(value: object) -> str:
    return " > ".join(
        " ".join(tokenize_text(part))
        for part in clean_text(value).split(">")
        if tokenize_text(part)
    )


def tokenize_text(value: object) -> list[str]:
    return [
        normalized
        for token in token_re.findall(clean_text(strip_html_tags(value)).casefold())
        if token != "s" and (normalized := normalize_taxonomy_token(token))  # nosec B105
    ]


def normalize_taxonomy_token(value: object) -> str:
    """Normalize taxonomy match tokens while preserving one-letter sizes."""
    token = str(value or "").strip().casefold()
    if token in {"handbag", "handbags"}:
        return "bag"
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("sses"):
        return token[:-2]
    if len(token) > 4 and token.endswith(("xes", "ches", "shes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
