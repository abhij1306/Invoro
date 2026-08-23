from __future__ import annotations

import httpx
import pytest

from app.services.domain_memory_service import load_domain_memory, save_domain_memory
from app.services.url_safety import PublicRequestTarget
from app.services.selectors_runtime import (
    coerce_int,
    create_selector_record,
    fetch_selector_document,
    list_selector_records,
    update_selector_record,
)


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_selector_record_uses_global_unique_ids(db_session) -> None:
    first = await create_selector_record(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        payload={
            "field_name": "title",
            "css_selector": "h1",
            "source": "manual",
        },
    )
    second = await create_selector_record(
        db_session,
        domain="other.example",
        surface="ecommerce_detail",
        payload={
            "field_name": "price",
            "css_selector": ".price",
            "source": "manual",
        },
    )

    assert first["id"] == 1
    assert second["id"] == 2


@pytest.mark.asyncio
@pytest.mark.component
async def test_create_selector_record_normalizes_duplicate_ids_before_append(
    db_session,
) -> None:
    await save_domain_memory(
        db_session,
        domain="one.example",
        surface="ecommerce_detail",
        selectors={
            "rules": [
                {"id": 1, "field_name": "title", "css_selector": "h1"},
            ]
        },
    )
    await save_domain_memory(
        db_session,
        domain="two.example",
        surface="ecommerce_detail",
        selectors={
            "rules": [
                {"id": 1, "field_name": "price", "css_selector": ".price"},
            ]
        },
    )
    await db_session.commit()

    created = await create_selector_record(
        db_session,
        domain="three.example",
        surface="ecommerce_detail",
        payload={
            "field_name": "brand",
            "css_selector": ".brand",
            "source": "manual",
        },
    )
    second_memory = await load_domain_memory(
        db_session,
        domain="two.example",
        surface="ecommerce_detail",
    )

    assert created["id"] == 3
    assert second_memory is not None
    assert second_memory.selectors["rules"][0]["id"] == 2


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_selector_document_rejects_private_targets() -> None:
    with pytest.raises(ValueError):
        await fetch_selector_document("http://localhost/internal")


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_selector_document_revalidates_promoted_iframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Result:
        final_url = "https://example.com/page"
        text = '<html><iframe src="http://127.0.0.1/internal"></iframe></html>'
        status_code = 200
        headers = httpx.Headers()

    async def _fake_request_result(url: str, **kwargs):
        assert url == "https://93.184.216.34:443/page"
        assert kwargs["headers"] == {"Host": "example.com"}
        assert kwargs["extensions"] == {"sni_hostname": "example.com"}
        return _Result()

    async def _fake_prepare(url: str):
        if url == "https://example.com/page":
            return PublicRequestTarget(
                logical_url=url,
                pinned_url="https://93.184.216.34:443/page",
                host_header="example.com",
                sni_hostname="example.com",
            )
        raise ValueError("Target host resolves to a non-public IP address")

    monkeypatch.setattr(
        "app.services.selectors_runtime.request_result", _fake_request_result
    )
    monkeypatch.setattr(
        "app.services.selectors_runtime.prepare_public_request_target", _fake_prepare
    )

    with pytest.raises(ValueError, match="non-public IP"):
        await fetch_selector_document("https://example.com/page")


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_selector_document_rejects_private_redirect_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    class _Redirect:
        final_url = "https://example.com/page"
        text = ""
        status_code = 302
        headers = httpx.Headers({"location": "http://127.0.0.1/internal"})

    async def _fake_request_result(url: str, **kwargs):
        assert kwargs["follow_redirects"] is False
        requested.append(url)
        return _Redirect()

    async def _fake_prepare(url: str):
        if url == "https://example.com/page":
            return PublicRequestTarget(
                logical_url=url,
                pinned_url="https://93.184.216.34:443/page",
                host_header="example.com",
                sni_hostname="example.com",
            )
        raise ValueError("Target host resolves to a non-public IP address")

    monkeypatch.setattr(
        "app.services.selectors_runtime.request_result", _fake_request_result
    )
    monkeypatch.setattr(
        "app.services.selectors_runtime.prepare_public_request_target", _fake_prepare
    )

    with pytest.raises(ValueError, match="non-public IP"):
        await fetch_selector_document("https://example.com/page")

    assert requested == ["https://93.184.216.34:443/page"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_update_selector_record_returns_committed_memory_timestamps(
    db_session,
) -> None:
    created = await create_selector_record(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        payload={
            "field_name": "title",
            "css_selector": "h1",
            "source": "manual",
        },
    )

    updated = await update_selector_record(
        db_session,
        selector_id=created["id"],
        payload={"sample_value": "Widget Prime"},
    )
    memory = await load_domain_memory(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
    )

    assert updated is not None
    assert memory is not None
    assert updated["updated_at"] == memory.updated_at


@pytest.mark.asyncio
@pytest.mark.component
async def test_list_selector_records_without_surface_returns_all_domain_surfaces(
    db_session,
) -> None:
    await create_selector_record(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        payload={
            "field_name": "title",
            "css_selector": "h1",
            "source": "manual",
        },
    )
    await create_selector_record(
        db_session,
        domain="example.com",
        surface="job_detail",
        payload={
            "field_name": "title",
            "css_selector": ".job-title",
            "source": "manual",
        },
    )

    rows = await list_selector_records(
        db_session,
        domain="example.com",
    )

    assert {(row["surface"], row["field_name"]) for row in rows} == {
        ("ecommerce_detail", "title"),
        ("job_detail", "title"),
    }


@pytest.mark.component
def test_coerce_int_preserves_zero() -> None:
    assert coerce_int(0, default=9) == 0
    assert coerce_int(" 0 ", default=9) == 0
