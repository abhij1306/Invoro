from __future__ import annotations

from types import SimpleNamespace

import pytest

from run_extraction_smoke import (
    _evaluate_detail_records,
    _json_response_issue,
)
from app.services.extract.detail.identity.identity_codes import (
    detail_identity_codes_from_record_fields,
)


@pytest.mark.unit
def test_json_response_issue_rejects_http_and_payload_errors() -> None:
    assert "HTTP 500" in str(
        _json_response_issue(SimpleNamespace(status_code=500, json_data={}))
    )
    assert _json_response_issue(
        SimpleNamespace(status_code=200, json_data={"success": False})
    )
    assert _json_response_issue(
        SimpleNamespace(status_code=200, json_data={"errors": ["unavailable"]})
    )
    assert (
        _json_response_issue(SimpleNamespace(status_code=200, json_data={"items": []}))
        is None
    )


@pytest.mark.unit
def test_detail_smoke_requires_an_extracted_record() -> None:
    result: dict[str, object] = {}

    _evaluate_detail_records(result, site={}, records=[])

    assert result["ok"] is False
    assert result["issue"] == "Expected at least one detail record, got 0"


@pytest.mark.unit
def test_detail_identity_codes_include_barcode() -> None:
    assert detail_identity_codes_from_record_fields({"barcode": "0123456789012"}) == {
        "0123456789012"
    }
