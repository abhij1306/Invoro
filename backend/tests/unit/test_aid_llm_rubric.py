from __future__ import annotations

import pytest

from app.services.config import aid_score as config
from app.services.ucp_audit.llm_rubric import RubricVerdict, parse_rubric_payload


@pytest.mark.unit
def test_parse_rubric_payload_downgrades_missing_evidence_quote() -> None:
    result = parse_rubric_payload(
        {
            "url": "https://example.com/p/1",
            "findings": [
                {
                    "dimension": "semantic_identity",
                    "verdict": "FAIL",
                    "evidence_quote": "",
                    "finding_code": config.FINDING_AID_LLM_IDENTITY_UNCLEAR,
                    "recommendation": "Add clear product facts.",
                }
            ],
            "simulated_queries": [{"query": "best tee for summer India", "answerable": False, "gap": "fabric"}],
            "error": "",
        },
        fallback_url="https://example.com/p/1",
    )

    assert result.findings[0].verdict == RubricVerdict.INSUFFICIENT_EVIDENCE
    assert result.simulated_queries[0].gap == "fabric"


@pytest.mark.unit
def test_parse_rubric_payload_accepts_null_evidence_quote() -> None:
    result = parse_rubric_payload(
        {
            "url": "https://example.com/p/1",
            "findings": [
                {
                    "dimension": "description_quality",
                    "verdict": "PARTIAL",
                    "evidence_quote": None,
                    "finding_code": config.FINDING_AID_LLM_DESCRIPTION_SHORT,
                    "recommendation": "Add fabric and care details.",
                }
            ],
            "simulated_queries": [],
            "error": "",
        },
        fallback_url="https://example.com/p/1",
    )

    assert result.findings[0].verdict == RubricVerdict.INSUFFICIENT_EVIDENCE
