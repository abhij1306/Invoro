import asyncio
import logging
from dataclasses import dataclass

from app.services.acquisition.browser_diagnostics import (
    build_failed_browser_diagnostics,
)
from app.services.acquisition.browser_pool import real_chrome_browser_available
from app.services.acquisition.browser_proxy_config import display_proxy, proxy_scheme
from app.services.acquisition.host_protection_memory import (
    load_host_protection_policy,
    note_host_hard_block,
)
from app.services.acquisition.pacing import wait_for_host_slot
from app.services.config.runtime_settings import (
    crawler_runtime_settings,
    proxy_rotation_mode,
)
from app.services.fetch.browser_policy import (
    attach_exception_browser_diagnostics,
    browser_attempt_timeout_seconds,
    browser_engine_attempts,
    build_browser_attempt_plan,
    extend_browser_engine_attempts_after_block,
    extract_vendor_from_reason,
    host_policy_snapshot,
    is_vendor_block_reason,
    should_retry_patchright_with_real_chrome,
)
from app.services.fetch.host_memory import record_fetch_result

logger = logging.getLogger(__name__)


@dataclass
class _AttemptRunner:
    context: object
    reason: str
    browser_fetcher: object
    emit_event: object
    fields: list[str]
    recovery_mode: str | None
    capture_screenshot: bool
    engine_selector: object
    real_chrome_available: object
    wait_for_slot: object
    record_result: object
    record_hard_block: object
    policy_loader: object
    host_policy: object = None
    last_error: Exception | None = None
    last_blocked: object = None

    async def run(self, proxies, supplied_policy):
        self.host_policy = supplied_policy or self.context.host_policy
        if self.host_policy is None:
            self.host_policy = await self._load_policy(self.context.url)
        self.context.host_policy = self.host_policy
        for proxy_index, proxy in enumerate(proxies, start=1):
            result = await self._run_proxy(proxy, proxy_index)
            if result is not None:
                return result
        if self.last_blocked is not None:
            return self.last_blocked
        if self.last_error is not None:
            attach_exception_browser_diagnostics(
                self.last_error, self.context.last_browser_attempt_diagnostics
            )
            raise self.last_error
        raise RuntimeError(f"Failed to fetch {self.context.url} in browser")

    async def _run_proxy(self, proxy, proxy_index):
        plan = build_browser_attempt_plan(
            context=self.context,
            host_policy=self.host_policy,
            reason=self.reason,
            proxy=proxy,
            proxy_attempt_index=proxy_index,
            real_chrome_available=self.real_chrome_available(),
            engine_selector=self.engine_selector,
        )
        engines = list(plan.engine_attempts)
        engine_index = 0
        while engine_index < len(engines):
            engine = engines[engine_index]
            engine_index += 1
            snapshot = host_policy_snapshot(self.host_policy)
            try:
                result = await self._fetch_engine(
                    proxy,
                    proxy_index,
                    engine,
                    engine_index,
                    engines,
                    plan.escalation_lane,
                    snapshot,
                )
            except Exception as exc:
                self.last_error = exc
                await self._handle_failure(
                    exc,
                    proxy,
                    proxy_index,
                    engine,
                    engine_index,
                    engines,
                    plan.escalation_lane,
                    snapshot,
                )
                continue
            if not result.blocked:
                return result
            self.last_blocked = result
            await self.record_result(self.context, result=result)
            self.host_policy = await self._load_policy(
                result.final_url or result.url or self.context.url
            )
            engines[:] = self._extended_engines(engines, engine)
            if engine_index < len(engines):
                await _post_block_cooldown()
        return None

    async def _fetch_engine(
        self, proxy, proxy_index, engine, engine_index, engines, lane, snapshot
    ):
        self._budget(engine, engines, "start")
        await self.wait_for_slot(
            self.context.url, ttl_seconds=self.context.host_memory_ttl_seconds
        )
        result = await self.browser_fetcher(
            self.context.url,
            self._budget(engine, engines, "run"),
            run_id=self.context.run_id,
            proxy=proxy,
            browser_engine=engine,
            browser_reason=self.reason,
            escalation_lane=lane,
            host_policy_snapshot=snapshot,
            proxy_profile=self.context.proxy_profile,
            locality_profile=self.context.locality_profile,
            surface=self.context.surface,
            traversal_mode=self.context.traversal_mode,
            requested_fields=self.fields,
            listing_recovery_mode=self.recovery_mode,
            capture_screenshot=self.capture_screenshot,
            max_pages=self.context.max_pages,
            max_scrolls=self.context.max_scrolls,
            max_records=self.context.max_records,
            on_event=self.context.on_event,
        )
        result.browser_diagnostics = {
            **dict(result.browser_diagnostics or {}),
            "proxy_url_redacted": display_proxy(proxy),
            "proxy_scheme": proxy_scheme(proxy),
            "browser_proxy_mode": "launch" if proxy else "direct",
            "proxy_attempt_index": proxy_index,
            "engine_attempt_index": engine_index,
            "proxy_rotation_mode": proxy_rotation_mode(self.context.proxy_profile),
        }
        return result

    def _budget(self, engine, engines, phase):
        remaining = browser_attempt_timeout_seconds(
            self.context,
            reason=self.reason,
            browser_engine=engine,
            engine_attempts=engines,
            host_policy=self.host_policy,
        )
        if remaining <= 0:
            raise TimeoutError(
                f"Acquisition browser retry budget exhausted before {engine} could {phase}"
            )
        return remaining

    async def _handle_failure(
        self, exc, proxy, proxy_index, engine, engine_index, engines, lane, snapshot
    ):
        diagnostics = build_failed_browser_diagnostics(
            browser_reason=self.reason,
            exc=exc,
            proxy=proxy,
            proxy_attempt_index=proxy_index,
            browser_engine=engine,
            browser_binary=engine,
            bridge_used=proxy_scheme(proxy) in {"socks5", "socks5h"},
            escalation_lane=lane,
            host_policy_snapshot=snapshot,
        )
        self.context.last_browser_attempt_diagnostics = diagnostics
        attach_exception_browser_diagnostics(exc, diagnostics)
        logger.debug(
            "Browser fetch failed: %s %s %s",
            self.context.url,
            proxy or "direct",
            engine,
            exc_info=True,
        )
        if should_retry_patchright_with_real_chrome(
            context=self.context,
            exc=exc,
            browser_engine=engine,
            engine_attempts=engines,
            real_chrome_available=self.real_chrome_available(),
        ):
            engines.append("real_chrome")
            await self.emit_event(
                self.context.on_event,
                "info",
                f"Patchright navigation failed for {self.context.url} with ERR_HTTP2_PROTOCOL_ERROR; retrying real Chrome",
            )
            return
        if not (
            isinstance(exc, (TimeoutError, asyncio.TimeoutError))
            and is_vendor_block_reason(self.reason)
        ):
            return
        await self.record_hard_block(
            self.context.url,
            method=f"browser:{engine}",
            vendor=extract_vendor_from_reason(self.reason),
            status_code=0,
            proxy_used=bool(proxy),
            ttl_seconds=self.context.host_memory_ttl_seconds,
        )
        self.host_policy = await self._load_policy(self.context.url)
        engines[:] = self._extended_engines(engines, engine)
        if engine_index < len(engines):
            await _post_block_cooldown()

    def _extended_engines(self, engines, attempted_engine):
        return extend_browser_engine_attempts_after_block(
            engine_attempts=engines,
            attempted_engine=attempted_engine,
            context=self.context,
            host_policy=self.host_policy,
            real_chrome_available=self.real_chrome_available(),
            engine_selector=self.engine_selector,
        )

    async def _load_policy(self, url):
        policy = await self.policy_loader(
            url, ttl_seconds=self.context.host_memory_ttl_seconds
        )
        self.context.host_policy = policy
        return policy


async def execute_browser_attempts(
    context,
    *,
    reason,
    browser_fetcher,
    emit_event,
    engine_selector=browser_engine_attempts,
    real_chrome_available=real_chrome_browser_available,
    wait_for_slot=wait_for_host_slot,
    record_result=record_fetch_result,
    record_hard_block=note_host_hard_block,
    policy_loader=load_host_protection_policy,
    requested_fields=None,
    listing_recovery_mode=None,
    capture_screenshot=False,
    proxies=None,
    host_policy=None,
):
    fields = list(
        context.requested_fields if requested_fields is None else requested_fields
    )
    recovery_source = (
        context.listing_recovery_mode
        if listing_recovery_mode is None
        else listing_recovery_mode
    )
    runner = _AttemptRunner(
        context,
        reason,
        browser_fetcher,
        emit_event,
        fields,
        str(recovery_source or "").strip() or None,
        capture_screenshot,
        engine_selector,
        real_chrome_available,
        wait_for_slot,
        record_result,
        record_hard_block,
        policy_loader,
    )
    return await runner.run(list(proxies or context.proxies), host_policy)


async def _post_block_cooldown() -> None:
    if (
        cooldown_ms := max(
            0, int(crawler_runtime_settings.browser_post_block_cooldown_ms or 0)
        )
    ) > 0:
        await asyncio.sleep(cooldown_ms / 1000)
