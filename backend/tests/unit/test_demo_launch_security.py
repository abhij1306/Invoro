from __future__ import annotations

from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from app.api.crawls import read_csv_upload
from app.main import application_routers
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.crawl.ingestion_service import build_csv_crawl_payload
from app.services.untrusted_html import trusted_origin, untrusted_html_response


@pytest.mark.asyncio
@pytest.mark.unit
async def test_csv_upload_accepts_exact_limit_and_rejects_extra_byte(
    monkeypatch,
) -> None:
    monkeypatch.setattr(crawler_runtime_settings, "csv_upload_max_bytes", 8)
    accepted = UploadFile(BytesIO(b"12345678"), headers=Headers())
    rejected = UploadFile(BytesIO(b"123456789"), headers=Headers())

    assert await read_csv_upload(accepted) == "12345678"
    with pytest.raises(Exception) as exc_info:
        await read_csv_upload(rejected)

    assert getattr(exc_info.value, "status_code", None) == 413


@pytest.mark.unit
def test_csv_payload_rejects_excess_url_count(monkeypatch) -> None:
    monkeypatch.setattr(crawler_runtime_settings, "csv_url_max_count", 2)
    csv_content = (
        "url\nhttps://one.example\nhttps://two.example\nhttps://three.example\n"
    )

    with pytest.raises(ValueError, match="2-URL limit"):
        build_csv_crawl_payload(csv_content=csv_content, surface="generic")


@pytest.mark.unit
def test_untrusted_html_response_blocks_active_content_and_framing() -> None:
    response = untrusted_html_response("<script>fetch('/api/health')</script>")
    csp = response.headers["content-security-policy"]

    assert "sandbox" in csp
    assert "script-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.unit
def test_trusted_origin_preserves_ipv6_brackets_and_regular_hosts() -> None:
    assert trusted_origin("http://[::1]:4000/path") == "http://[::1]:4000"
    assert trusted_origin("https://invoro.example/path") == "https://invoro.example"


@pytest.mark.unit
def test_monitoring_disabled_router_set_omits_all_monitoring_surfaces() -> None:
    paths = {
        route.path
        for router in application_routers(monitoring_enabled=False)
        for route in router.routes
    }

    assert not any(path.startswith("/api/monitors") for path in paths)
    assert not any(path.startswith("/api/alerts") for path in paths)
    assert not any(path.startswith("/api/notifications") for path in paths)
    assert not any(path.startswith("/api/v1/alerts") for path in paths)
