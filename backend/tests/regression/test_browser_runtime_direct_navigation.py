from __future__ import annotations

from .test_browser_expansion_runtime import CARD_SELECTORS, PlaywrightError, PlaywrightTimeoutError, TraversalResult, _FakeExpansionPage, _FakeRuntime, _async_checkpoint, asynccontextmanager, asyncio, browser_pool, browser_runtime, pytest  # fmt: skip

pytest_plugins = ["tests.regression.test_browser_expansion_runtime"]


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.parametrize("browser_engine", ["patchright", "real_chrome"])
async def test_browser_fetch_navigates_directly_to_target(
    browser_engine: str,
) -> None:
    target_url = "https://example.com/products/widget"
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget</h1><p>Product detail content</p></body></html>"
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        target_url,
        5,
        surface="ecommerce_detail",
        browser_engine=browser_engine,
        browser_reason="http-escalation",
        runtime_provider=_fake_runtime,
    )

    assert result.status_code == 200
    assert page.goto_url_calls == [target_url]
    assert not page.spawned_pages


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
