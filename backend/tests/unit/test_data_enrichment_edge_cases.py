from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.config.data_enrichment import DATA_ENRICHMENT_STATUS_FAILED
from app.services.data_enrichment.job_execution import process_product_ref
from app.services.data_enrichment.options import as_int, bounded_int


@pytest.mark.unit
def test_data_enrichment_integer_options_reject_infinity() -> None:
    assert bounded_int(float("inf"), 7, ceiling=20) == 7
    assert as_int(float("-inf")) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_missing_source_record_failure_is_committed() -> None:
    product = SimpleNamespace(status="pending", diagnostics={})
    session = AsyncMock()
    session.get.side_effect = [product, None]

    job, succeeded = await process_product_ref(
        session,
        job=SimpleNamespace(),
        job_id=1,
        product_id=2,
        source_record_id=3,
        llm_enabled=False,
        enrich_product=AsyncMock(),
    )

    assert job is not None
    assert succeeded is False
    assert product.status == DATA_ENRICHMENT_STATUS_FAILED
    assert product.diagnostics == {"error": "source_record_missing"}
    session.commit.assert_awaited_once()
