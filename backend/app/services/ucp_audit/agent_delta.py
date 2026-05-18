from __future__ import annotations

from typing import Any

from app.services.acquisition.acquirer import AcquisitionRequest, acquire
from app.services.acquisition.policy import AcquisitionPolicy
from app.services.acquisition_plan import AcquisitionPlan
from app.services.config import ucp_audit as config
from app.services.pipeline.extract_records import extract_records
from app.services.ucp_audit.product_schema import score_product_schema
from app.services.ucp_audit.types import AgentViewDelta


async def build_agent_view_delta(url: str) -> AgentViewDelta:
    structured = await acquire_url(url, mode=config.UCP_HTTP_ONLY_MODE)
    rendered = await acquire_url(url, mode=config.UCP_BROWSER_ONLY_MODE)
    agent = extract_agent_view(str(getattr(structured, "html", "") or ""), url)
    human = extract_human_view(str(getattr(rendered, "html", "") or ""), url)
    agent_keys = set(agent)
    human_keys = set(human)
    return AgentViewDelta(
        url=url,
        agent_extracted=agent,
        human_visible=human,
        missing_in_agent_view=sorted(human_keys - agent_keys),
        agent_only_signals=sorted(agent_keys - human_keys),
        fidelity_score=compute_fidelity_score(agent, human),
    )


async def acquire_url(url: str, *, mode: str):
    request = AcquisitionRequest(
        run_id=0,
        url=url,
        plan=AcquisitionPlan(surface=config.UCP_AUDIT_SURFACE),
        policy=AcquisitionPolicy(fetch_mode=mode),
    )
    return await acquire(request)


# UA override is not supported by acquisition layer yet.
# This compares default HTTP structured evidence with browser-rendered evidence.
def extract_agent_view(html: str, url: str) -> dict[str, Any]:
    score = score_product_schema(url, html)
    values: dict[str, Any] = {}
    for label in score.required_fields_present + score.recommended_fields_present:
        values[label.rsplit(".", 1)[-1]] = True
    if config.JSON_LD_NAME_FIELD in score.required_fields_present:
        values[config.JSON_LD_NAME_FIELD] = _name_from_html(html, url)
    return {key: value for key, value in values.items() if value not in (None, "")}


def extract_human_view(html: str, url: str) -> dict[str, Any]:
    records = extract_records(
        html,
        url,
        config.UCP_AUDIT_SURFACE,
        max_records=1,
        requested_page_url=url,
    )
    first = records[0] if records else {}
    return dict(first) if isinstance(first, dict) else {}


def compute_fidelity_score(agent: dict[str, Any], human: dict[str, Any]) -> float:
    human_keys = set(human)
    if not human_keys:
        return 1.0
    return round(len(set(agent) & human_keys) / len(human_keys), 4)


def _name_from_html(html: str, url: str) -> str | None:
    del url
    score = score_product_schema("", html)
    if config.JSON_LD_NAME_FIELD not in score.required_fields_present:
        return None
    from bs4 import BeautifulSoup
    from app.services.structured_sources import parse_json_ld

    for item in parse_json_ld(BeautifulSoup(str(html or ""), "html.parser")):
        value = item.get(config.JSON_LD_NAME_FIELD) if isinstance(item, dict) else None
        if value not in (None, "", [], {}):
            return str(value)
    return None
