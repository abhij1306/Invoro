from __future__ import annotations

from .test_browser_expansion_runtime import CARD_SELECTORS, PlaywrightError, PlaywrightTimeoutError, TraversalResult, _FakeExpansionPage, _FakeRuntime, _async_checkpoint, asynccontextmanager, asyncio, browser_pool, browser_runtime, cookie_store, pytest  # fmt: skip
from app.services.acquisition import browser_origin_warmup

pytest_plugins = ["tests.regression.test_browser_expansion_runtime"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_skips_recovery_after_budget_is_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Page:
        async def goto(self, *args, **kwargs):
            del args, kwargs
            return object()

    async def _unexpected_recovery(*args, **kwargs):
        del args, kwargs
        raise AssertionError("challenge recovery must not exceed warmup budget")

    monkeypatch.setattr(browser_origin_warmup, "elapsed_ms", lambda _started: 1000)
    monkeypatch.setattr(
        browser_origin_warmup, "recover_browser_challenge", _unexpected_recovery
    )

    timings = await browser_origin_warmup._navigate_warmup_page(
        _Page(),
        warm_url="https://example.com/",
        browser_engine="chromium",
        warm_budget_ms=1000,
        started_at=0,
    )

    assert timings == {}


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_skips_for_rotating_proxy_profile() -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_reason="http-escalation",
        host_policy_snapshot=None,
        proxy_profile={"rotation": "rotating"},
        timeout_seconds=5,
        phase_timings_ms={},
    )

    assert page.goto_calls == []
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_runs_for_real_chrome_without_saved_domain_state() -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="http-escalation",
        host_policy_snapshot=None,
        proxy_profile=None,
        timeout_seconds=5,
        phase_timings_ms={},
    )

    assert page.goto_calls == ["domcontentloaded"]
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_caps_budget_to_preserve_navigation_time(
    patch_settings,
) -> None:
    patch_settings(
        origin_warmup_max_budget_ratio=0.4,
        browser_navigation_domcontentloaded_timeout_ms=15000,
    )
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="vendor-block:akamai",
        host_policy_snapshot=None,
        proxy_profile=None,
        timeout_seconds=20,
        phase_timings_ms={},
    )

    assert page.goto_timeout_calls == [8000]
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_keeps_minimum_budget_for_short_url_timeout(
    patch_settings,
) -> None:
    patch_settings(
        origin_warmup_max_budget_ratio=0.4,
        browser_navigation_domcontentloaded_timeout_ms=15000,
    )
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="http-escalation",
        host_policy_snapshot=None,
        proxy_profile=None,
        timeout_seconds=1,
        phase_timings_ms={},
    )

    assert page.goto_timeout_calls == [750]
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_zero_ratio_preserves_minimum_budget(
    patch_settings,
) -> None:
    patch_settings(
        origin_warmup_max_budget_ratio=0,
        browser_navigation_domcontentloaded_timeout_ms=15000,
    )
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="http-escalation",
        host_policy_snapshot=None,
        proxy_profile=None,
        timeout_seconds=10,
        phase_timings_ms={},
    )

    assert page.goto_timeout_calls == [750]
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_skips_for_real_chrome_with_saved_domain_state() -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="http-escalation",
        host_policy_snapshot=None,
        proxy_profile=None,
        skip_for_reusable_domain_state=True,
        timeout_seconds=5,
        phase_timings_ms={},
    )

    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_skips_for_known_vendor_block_memory() -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_reason="host-preference",
        host_policy_snapshot={"prefer_browser": True, "last_block_vendor": "datadome"},
        proxy_profile=None,
        timeout_seconds=5,
        phase_timings_ms={},
    )

    assert page.goto_calls == []
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_runs_for_real_chrome_despite_vendor_block_memory() -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")

    await browser_runtime._maybe_warm_origin_before_navigation(
        page,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="vendor-block:datadome",
        host_policy_snapshot={"prefer_browser": True, "last_block_vendor": "datadome"},
        proxy_profile=None,
        timeout_seconds=5,
        phase_timings_ms={},
    )

    assert page.goto_calls == ["domcontentloaded"]
    assert not page.spawned_pages


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_dedupes_parallel_same_host() -> None:
    pages = [
        _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")
        for _index in range(6)
    ]

    await asyncio.gather(
        *(
            browser_runtime._maybe_warm_origin_before_navigation(
                page,
                url="https://example.com/products/widget",
                surface="ecommerce_detail",
                browser_reason="http-escalation",
                host_policy_snapshot=None,
                proxy_profile=None,
                timeout_seconds=5,
                phase_timings_ms={},
            )
            for page in pages
        )
    )

    assert sum(len(page.spawned_pages) for page in pages) == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_origin_warmup_dedupes_recent_same_host_waves_by_default() -> None:
    pages = [
        _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")
        for _index in range(3)
    ]

    for page in pages:
        await browser_runtime._maybe_warm_origin_before_navigation(
            page,
            url="https://example.com/products/widget",
            surface="ecommerce_detail",
            browser_reason="http-escalation",
            host_policy_snapshot=None,
            proxy_profile=None,
            timeout_seconds=5,
            phase_timings_ms={},
        )

    assert sum(len(page.spawned_pages) for page in pages) == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_skips_real_chrome_warmup_when_domain_cookies_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(base_html="<html><body><h1>Widget</h1></body></html>")
    captured_skip_flags: list[bool] = []

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_load_storage_state_for_domain(*_args, **_kwargs):
        await _async_checkpoint()
        return {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc",
                    "domain": ".example.com",
                    "path": "/",
                }
            ],
            "origins": [],
        }

    async def _fake_warm_origin(*_args, **kwargs):
        await _async_checkpoint()
        captured_skip_flags.append(bool(kwargs.get("skip_for_reusable_domain_state")))

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_domain",
        _fake_load_storage_state_for_domain,
    )
    monkeypatch.setattr(
        browser_runtime,
        "_maybe_warm_origin_before_navigation",
        _fake_warm_origin,
    )

    await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        browser_engine="real_chrome",
        browser_reason="http-escalation",
        runtime_provider=_fake_runtime,
    )

    assert captured_skip_flags == [True]


@pytest.mark.regression
def test_browser_runtime_snapshot_uses_capacity_fallback_for_pooled_runtimes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeRuntime:
        def snapshot(self) -> dict[str, int | bool]:
            return {
                "ready": True,
                "size": 1,
                "active": 1,
                "queued": 0,
                "capacity": 3,
            }

        async def close(self) -> None:
            await _async_checkpoint()
            return None

    monkeypatch.setattr(
        browser_pool._BROWSER_POOL, "direct", {"direct": _FakeRuntime()}
    )
    monkeypatch.setattr(
        browser_pool._BROWSER_POOL, "proxied", {"proxy": _FakeRuntime()}
    )

    snapshot = browser_runtime.browser_runtime_snapshot()

    assert snapshot["capacity"] == 6
    assert snapshot["max_size"] == 6


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_disables_storage_reuse_for_rotating_proxy_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_allow_storage_state: list[bool] = []

    class _StopFetch(Exception):
        pass

    @asynccontextmanager
    async def _fake_page_context():
        await _async_checkpoint()
        if len(captured_allow_storage_state) < 0:
            yield
        raise _StopFetch

    def _fake_resolve_proxied_page_factory(*args, **kwargs):
        del args
        captured_allow_storage_state.append(bool(kwargs["allow_storage_state"]))
        return _fake_page_context()

    monkeypatch.setattr(
        browser_runtime,
        "_resolve_proxied_page_factory",
        _fake_resolve_proxied_page_factory,
    )

    with pytest.raises(_StopFetch):
        await browser_runtime.browser_fetch(
            "https://example.com/products/widget",
            5,
            proxy="http://proxy.example:8080",
            proxy_profile={"rotation": "rotating"},
            surface="ecommerce_detail",
            proxied_page_factory=lambda **_: None,
        )

    assert captured_allow_storage_state == [False]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_recovers_when_commit_navigation_is_interrupted_by_same_url_reload() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget</h1></body></html>",
        goto_failures={
            "domcontentloaded": PlaywrightTimeoutError("primary timeout"),
            "commit": PlaywrightError(
                'Navigation to "https://example.com/products/widget" is interrupted '
                'by another navigation to "https://example.com/products/widget"'
            ),
        },
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert page.goto_calls == ["domcontentloaded", "commit"]
    assert "domcontentloaded" in page.load_state_calls
    assert result.final_url == "https://example.com/products/widget"
    assert result.status_code == 0


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_force_closes_context_when_cancelled_mid_stage() -> None:
    content_entered = asyncio.Event()
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget</h1></body></html>",
        content_blocker=asyncio.Event(),
        ignore_content_cancellation=True,
        content_entered=content_entered,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    task = asyncio.create_task(
        browser_runtime.browser_fetch(
            "https://example.com/products/widget",
            5,
            surface="ecommerce_detail",
            runtime_provider=_fake_runtime,
        )
    )

    async with asyncio.timeout(0.5):
        await content_entered.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(0.5):
            await asyncio.wait_for(task, timeout=0.5)

    assert page.page_close_calls + page.context_close_calls >= 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_force_closes_context_when_stage_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget</h1></body></html>",
        content_blocker=asyncio.Event(),
        content_block_after_calls=1,
        ignore_content_cancellation=True,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    remaining_timeouts = iter([5.0, 0.05, 0.05, 0.05])

    def _remaining_timeout() -> float:
        try:
            return remaining_timeouts.__next__()
        except StopIteration:
            return 0.05

    monkeypatch.setattr(
        browser_runtime,
        "remaining_timeout_factory",
        lambda _deadline: _remaining_timeout,
    )

    with pytest.raises(TimeoutError, match="Browser settle stage exceeded") as excinfo:
        async with asyncio.timeout(0.5):
            await browser_runtime.browser_fetch(
                "https://example.com/products/widget",
                5,
                surface="ecommerce_detail",
                browser_reason="http-escalation",
                runtime_provider=_fake_runtime,
            )

    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=excinfo.value,
    )

    assert page.page_close_calls + page.context_close_calls >= 1
    assert diagnostics["failure_stage"] == "settle"
    assert diagnostics["browser_outcome"] == "render_timeout"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_surfaces_traversal_fragment_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>"
            "</body></html>"
        ),
        selector_counts={".product-card": 2},
        card_count=2,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_execute_listing_traversal(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            progress_events=1,
            pages_advanced=1,
            card_count=2,
            html_fragments=[
                (
                    "<div data-traversal-cards='true'><article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article></div>",
                    False,
                ),
                (
                    "<div data-traversal-cards='true'><article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article></div>",
                    False,
                ),
            ],
        )

    monkeypatch.setattr(
        browser_runtime,
        "execute_listing_traversal",
        _fake_execute_listing_traversal,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        runtime_provider=_fake_runtime,
    )

    assert result.browser_diagnostics["traversal_fragment_count"] == 2
    assert result.browser_diagnostics["traversal_html_bytes"] == sum(
        len(fragment.encode("utf-8"))
        for fragment in [
            "<div data-traversal-cards='true'><article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article></div>",
            "<div data-traversal-cards='true'><article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article></div>",
        ]
    )
    assert 'data-traversal-fragment="1"' in result.html
    assert 'data-traversal-fragment="2"' in result.html


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_keeps_full_rendered_html_when_traversal_makes_no_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selectors = list(CARD_SELECTORS.get("ecommerce") or [])
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>"
            "<article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>"
            "<article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>"
            "</body></html>"
        ),
        selector_counts={selectors[0]: 3} if selectors else {},
        card_count=3,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_execute_listing_traversal(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="next_page_not_found",
            progress_events=0,
            card_count=5,
            html_fragments=[
                (
                    "<div data-traversal-cards='true'><a href='/privacy'>Privacy notice</a></div>",
                    False,
                ),
            ],
        )

    monkeypatch.setattr(
        browser_runtime,
        "execute_listing_traversal",
        _fake_execute_listing_traversal,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        runtime_provider=_fake_runtime,
    )

    assert "Widget One" in result.html
    assert "Privacy notice" not in result.html
    assert "traversal_composed_html" in result.artifacts
    assert "Privacy notice" in result.artifacts["traversal_composed_html"]
    assert result.browser_diagnostics["browser_outcome"] == "usable_content"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_prefers_rendered_html_when_progress_traversal_fragment_is_thin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selectors = list(CARD_SELECTORS.get("ecommerce") or [])
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>"
            "<article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>"
            "<article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>"
            "</body></html>"
        ),
        selector_counts={selectors[0]: 3} if selectors else {},
        card_count=3,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_execute_listing_traversal(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="paginate_progressed",
            progress_events=1,
            card_count=0,
            html_fragments=[
                (
                    "<div data-traversal-cards='true'><a href='/products/widget-1'>Widget One</a></div>",
                    False,
                ),
            ],
        )

    monkeypatch.setattr(
        browser_runtime,
        "execute_listing_traversal",
        _fake_execute_listing_traversal,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        runtime_provider=_fake_runtime,
    )

    assert "Widget Two" in result.html
    assert "traversal_composed_html" in result.artifacts
    assert "Widget Two" in result.artifacts["full_rendered_html"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_runs_listing_recovery_when_thin_listing_retry_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<button>View all</button>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a></article>"
            "</body></html>"
        ),
    )
    page.url = "https://example.com/collections/widgets"
    calls = {"count": 0}

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_recover_listing_page_content(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        calls["count"] += 1
        return {
            "status": "recovered",
            "clicked_count": 1,
            "actions_taken": ["view_all"],
        }

    monkeypatch.setattr(
        browser_runtime,
        "recover_listing_page_content",
        _fake_recover_listing_page_content,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        listing_recovery_mode="thin-listing retry",
        runtime_provider=_fake_runtime,
    )

    assert calls["count"] == 1
    assert result.browser_diagnostics["listing_recovery"]["status"] == "recovered"
    assert (
        result.browser_diagnostics["listing_recovery"]["requested_mode"]
        == "thin_listing"
    )
