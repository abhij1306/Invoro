from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRun
from app.models.domain_memory import DomainMemory, DomainRunProfile
from app.schemas.public_api import PublicDomainInfo
from app.services.config.public_api import PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE, PUBLIC_API_SURFACE_ECOMMERCE
from app.services.domain_memory_service import selector_rules_from_memory
from app.services.domain_utils import normalize_domain


async def public_domain_info(session: AsyncSession, *, domain: str) -> PublicDomainInfo:
    normalized = normalize_domain(domain)
    memory = await _load_memory(session, normalized)
    profile = await _load_profile(session, normalized)
    last_crawled_at = await _last_crawled_at(session, normalized)
    known = memory is not None or profile is not None or last_crawled_at is not None
    return PublicDomainInfo(
        domain=normalized,
        known=known,
        surface=PUBLIC_API_SURFACE_ECOMMERCE if known else None,
        last_crawled_at=last_crawled_at,
        has_cached_selectors=_has_active_selectors(memory),
        acquisition_profile=_acquisition_profile(profile),
    )


async def _load_memory(session: AsyncSession, domain: str) -> DomainMemory | None:
    return await session.scalar(
        select(DomainMemory)
        .where(
            DomainMemory.domain == domain,
            DomainMemory.surface == PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE,
        )
        .order_by(DomainMemory.updated_at.desc(), DomainMemory.id.desc())
        .limit(1)
    )


async def _load_profile(session: AsyncSession, domain: str) -> DomainRunProfile | None:
    return await session.scalar(
        select(DomainRunProfile)
        .where(
            DomainRunProfile.domain == domain,
            DomainRunProfile.surface == PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE,
        )
        .order_by(DomainRunProfile.updated_at.desc(), DomainRunProfile.id.desc())
        .limit(1)
    )


async def _last_crawled_at(session: AsyncSession, domain: str) -> datetime | None:
    result = await session.execute(
        select(CrawlRun)
        .where(CrawlRun.surface == PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE)
        .order_by(CrawlRun.completed_at.desc().nullslast(), CrawlRun.created_at.desc())
        .limit(100)
    )
    for run in result.scalars().all():
        if normalize_domain(run.url) == domain:
            return run.completed_at or run.created_at
    return None


def _has_active_selectors(memory: DomainMemory | None) -> bool:
    return any(bool(row.get("is_active", True)) for row in selector_rules_from_memory(memory))


def _acquisition_profile(profile: DomainRunProfile | None) -> str:
    if profile is None:
        return "unknown"
    payload = dict(profile.profile or {})
    contract = dict(payload.get("acquisition_contract") or {})
    fetch_profile = dict(payload.get("fetch_profile") or {})
    if contract.get("required_rendering") or contract.get("prefer_browser"):
        return "browser_required"
    if fetch_profile or contract:
        return "http_preferred"
    return "unknown"
