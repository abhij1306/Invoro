from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from fastapi.responses import HTMLResponse


_SANDBOX_POLICY = (
    "sandbox; default-src 'none'; script-src 'none'; connect-src 'none'; "
    "object-src 'none'; frame-src 'none'; form-action 'none'; "
    "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src 'none'; "
    "base-uri http: https:"
)


def trusted_origin(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Trusted frame origin must be an absolute HTTP(S) URL")
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme}://{hostname}{port}"


def untrusted_html_response(
    content: str,
    *,
    frame_ancestors: Iterable[str] | None = None,
) -> HTMLResponse:
    ancestors = list(
        dict.fromkeys(trusted_origin(value) for value in frame_ancestors or [])
    )
    ancestor_policy = " ".join(ancestors) if ancestors else "'none'"
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"{_SANDBOX_POLICY}; frame-ancestors {ancestor_policy}"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
