from __future__ import annotations

import asyncio

from app.services.acquisition.acquirer import AcquisitionRequest, AcquisitionResult


def _as_async(fn):
    async def _wrapped(*args, **kwargs):
        await asyncio.sleep(0)
        return fn(*args, **kwargs)

    return _wrapped


def _detail_html() -> str:
    return "<html><body><h1>Widget Prime</h1></body></html>"


def _listing_html() -> str:
    return "<html><body><h1>Empty category</h1></body></html>"


def _fake_acquire_result(
    request: AcquisitionRequest,
    *,
    html: str | None = None,
    method: str = "test",
    status_code: int = 200,
    final_url: str | None = None,
    **overrides,
) -> AcquisitionResult:
    return AcquisitionResult(
        request=request,
        final_url=final_url or request.url,
        html=_detail_html() if html is None else html,
        method=method,
        status_code=status_code,
        **overrides,
    )


@_as_async
def _no_adapter(*_args, **_kwargs):
    return None


__all__ = [
    "_as_async",
    "_detail_html",
    "_fake_acquire_result",
    "_listing_html",
    "_no_adapter",
]
