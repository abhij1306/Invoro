from __future__ import annotations

from .test_traversal_runtime import Any, TraversalResult, _FakePage, _OverlayTestLocator, _OverlayTestPage, _State, count_listing_cards, dismiss_overlays_if_needed, execute_listing_traversal, listing_selector_is_weak, pytest, traversal_helpers, traversal_module, wait_for_load_more_card_gain  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.component
async def test_scroll_traversal_runs_when_explicitly_requested() -> None:
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs done</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="scroll",
        max_pages=2,
        max_scrolls=3,
    )

    assert result.selected_mode == "scroll"
    assert result.scroll_iterations >= 1
    assert result.progress_events >= 1
    assert result.card_count == 6
    assert [f for f, _ in result.html_fragments][:2] == [
        "<div>jobs</div>",
        "<div>jobs more</div>",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_scroll_traversal_stops_at_user_max_records() -> None:
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs too-far</div>",
                card_count=9,
                scroll_height=4200,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="scroll",
        max_pages=2,
        max_scrolls=3,
        max_records=6,
    )

    assert result.stop_reason == "target_records_reached"
    assert result.scroll_iterations == 1
    assert result.card_count == 6
    assert [f for f, _ in result.html_fragments][:2] == [
        "<div>jobs</div>",
        "<div>jobs more</div>",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_scroll_traversal_respects_max_scrolls_cap() -> None:
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs too-far</div>",
                card_count=9,
                scroll_height=4200,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="scroll",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.stop_reason == "scroll_limit_reached"
    assert result.scroll_iterations == 1
    assert result.card_count == 6
    assert [f for f, _ in result.html_fragments][:2] == [
        "<div>jobs</div>",
        "<div>jobs more</div>",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_execute_listing_traversal_ignores_invalid_timeout_value() -> None:
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="scroll",
        max_pages=2,
        max_scrolls=1,
        timeout_seconds="bad-timeout",
    )

    assert result.stop_reason == "scroll_limit_reached"
    assert result.scroll_iterations == 1
    assert result.card_count == 6


@pytest.mark.asyncio
@pytest.mark.component
async def test_execute_listing_traversal_rejects_unsupported_mode() -> None:
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="unsupported_mode",
        max_pages=2,
        max_scrolls=2,
    )

    assert result.selected_mode is None
    assert result.activated is False
    assert result.stop_reason == "unsupported_mode"
    assert result.scroll_iterations == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_click_transition_uses_networkidle_settle_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls={"next_page"},
            next_href="#",
            next_control_state={
                "raw_href": "#",
                "has_click_handler": True,
                "pagination_container": True,
                "pagination_text": True,
                "sibling_page_numbers": True,
                "is_button_like": False,
            },
        ),
        paginated_states=[
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls={"next_page"},
                next_href="#",
                next_control_state={
                    "raw_href": "#",
                    "has_click_handler": True,
                    "pagination_container": True,
                    "pagination_text": True,
                    "sibling_page_numbers": True,
                    "is_button_like": False,
                },
            ),
            _State(
                html="<div>page-2</div>",
                card_count=5,
                scroll_height=2800,
                client_height=600,
                controls=set(),
            ),
        ],
    )
    settle_timeouts: list[int] = []

    async def _capture_settle(page_arg, *, quiet_window_ms: int, timeout_ms: int):
        del page_arg, quiet_window_ms
        settle_timeouts.append(timeout_ms)
        return {"observed": True}

    monkeypatch.setattr(
        traversal_helpers, "_dom_wait_for_dom_mutation_settle", _capture_settle
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.pages_advanced == 1
    assert settle_timeouts
    assert max(settle_timeouts) >= int(
        traversal_module.crawler_runtime_settings.traversal_settle_networkidle_timeout_ms
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_scroll_traversal_emits_live_events() -> None:
    emitted: list[tuple[str, str]] = []
    page = _FakePage(
        surface="job_listing",
        initial_state=_State(
            html="<div>jobs</div>",
            card_count=2,
            scroll_height=2500,
            client_height=600,
            controls=set(),
        ),
        scroll_states=[
            _State(
                html="<div>jobs</div>",
                card_count=2,
                scroll_height=2500,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs more</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
            _State(
                html="<div>jobs done</div>",
                card_count=6,
                scroll_height=3400,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    async def _on_event(level: str, message: str) -> None:
        emitted.append((level, message))

    await execute_listing_traversal(
        page,
        surface="job_listing",
        traversal_mode="scroll",
        max_pages=2,
        max_scrolls=3,
        on_event=_on_event,
    )

    assert emitted[:2] == [
        ("info", "Detected listing layout, traversal=scroll, safety_cap=50"),
        ("info", "Scroll 1 - page_cards=6 (prev_page_cards=2)"),
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_detects_cycle_on_redirect_loop() -> None:
    """If a ?page=999 redirects back to ?page=1, the crawler must stop
    instead of infinite-looping until max_pages is hit."""
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1200,
            controls={"next_page"},
            next_href="https://example.com/listing?page=2",
        ),
        paginated_states=[
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=1200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=2",
            ),
            # Server redirects ?page=2 back to ?page=1 (cycle)
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=1200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=2",
            ),
        ],
    )
    # Simulate the redirect: goto sets url to ?page=2 but the fake page
    # state ends up identical to page-1.  Override url after goto to
    # simulate server-side redirect back to page-1.
    original_goto = page.goto

    async def _redirect_goto(url, **kw):
        await original_goto(url, **kw)
        page.url = "https://example.com/listing"  # redirected back

    page.goto = _redirect_goto

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=5,
        max_scrolls=1,
    )

    assert result.stop_reason == "paginate_cycle_detected"
    assert result.pages_advanced == 0


@pytest.mark.component
def test_is_same_origin_blocks_cross_tenant_paths() -> None:
    """Pagination must not bleed across path-based multi-tenant boundaries."""
    is_same_origin = traversal_module.is_same_origin

    assert is_same_origin(
        "https://myworkdayjobs.com/TenantA/jobs?page=1",
        "https://myworkdayjobs.com/TenantA/jobs?page=2",
    )
    assert not is_same_origin(
        "https://myworkdayjobs.com/TenantA/jobs?page=1",
        "https://myworkdayjobs.com/TenantB/jobs?page=1",
    )


@pytest.mark.component
def test_is_same_origin_blocks_cross_tenant_paths_for_workday_subdomains() -> None:
    is_same_origin = traversal_module.is_same_origin

    assert is_same_origin(
        "https://smithnephew.wd5.myworkdayjobs.com/TenantA/jobs?page=1",
        "https://smithnephew.wd5.myworkdayjobs.com/TenantA/jobs?page=2",
    )
    assert not is_same_origin(
        "https://smithnephew.wd5.myworkdayjobs.com/TenantA/jobs?page=1",
        "https://smithnephew.wd5.myworkdayjobs.com/TenantB/jobs?page=1",
    )


@pytest.mark.component
def test_is_same_origin_allows_same_tenant_different_pages() -> None:
    is_same_origin = traversal_module.is_same_origin

    assert is_same_origin(
        "https://example.com/listing?page=1",
        "https://example.com/listing?page=2",
    )
    assert not is_same_origin(
        "https://example.com/listing?page=1",
        "https://other.com/listing?page=2",
    )


@pytest.mark.component
def test_is_same_origin_allows_same_host_path_changes_outside_tenant_hosts() -> None:
    is_same_origin = traversal_module.is_same_origin

    assert is_same_origin(
        "https://example.com/careers?page=1",
        "https://example.com/jobs?page=2",
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_dismiss_overlays_targets_interceptors_not_structural_tags() -> None:
    page = _OverlayTestPage()
    locator = _OverlayTestLocator()
    result = TraversalResult(requested_mode="paginate")

    await dismiss_overlays_if_needed(page, locator=locator, result=result)

    assert result.overlays_dismissed is True
    assert locator.evaluate_calls
    script = locator.evaluate_calls[0]
    assert "elementsFromPoint" in script
    assert "const tags = ['header', 'footer', 'nav']" not in script


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_uses_myntra_card_selector() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="""
            <ul class="results-base">
              <li class="product-base"><a href="/a">A</a></li>
              <li class="product-base"><a href="/b">B</a></li>
              <li class="product-base"><a href="/c">C</a></li>
            </ul>
            """,
            card_count=3,
            scroll_height=1200,
            controls=set(),
        ),
    )

    count = await count_listing_cards(page, surface="ecommerce_listing")

    assert count == 3


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_uses_zara_product_grid_selector() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="""
            <ul class="product-grid">
              <li class="product-grid-product"><a href="/in/en/product-a-p0001.html">A</a></li>
              <li class="product-grid-product"><a href="/in/en/product-b-p0002.html">B</a></li>
            </ul>
            """,
            card_count=12,
            scroll_height=1600,
            controls=set(),
        ),
    )

    count = await count_listing_cards(page, surface="ecommerce_listing")

    assert count == 12


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_falls_back_to_heuristics_when_selectors_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ZeroLocator:
        async def count(self) -> int:
            return 0

    class _SelectorPage:
        def locator(self, selector: str) -> _ZeroLocator:
            del selector
            return _ZeroLocator()

        async def evaluate(self, script: str, arg: Any | None = None) -> int | None:
            del arg
            if "querySelectorAll(selector).length" in script:
                return 0
            return None

        async def content(self) -> str:
            return """
            <html>
              <body>
                <section class="results-grid">
                  <article class="product-card">
                    <a href="/products/widget-a"><img src="/a.jpg" alt="A" />Widget A</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-b"><img src="/b.jpg" alt="B" />Widget B</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-c"><img src="/c.jpg" alt="C" />Widget C</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-d"><img src="/d.jpg" alt="D" />Widget D</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-e"><img src="/e.jpg" alt="E" />Widget E</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-f"><img src="/f.jpg" alt="F" />Widget F</a>
                  </article>
                  <article class="product-card">
                    <a href="/products/widget-g"><img src="/g.jpg" alt="G" />Widget G</a>
                  </article>
                </section>
              </body>
            </html>
            """

    monkeypatch.setattr(
        "app.services.acquisition.traversal_card_counting.CARD_SELECTORS",
        {"ecommerce": [".product-card"], "jobs": [".job-card"]},
    )

    count = await count_listing_cards(_SelectorPage(), surface="ecommerce_listing")

    assert count == 7


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_ignores_weak_product_selector_chrome() -> None:
    class _WeakProductChromePage:
        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            assert "querySelectorAll(selector).length" in script
            return {
                selector: (2 if listing_selector_is_weak(str(selector)) else 0)
                for selector in list(arg or [])
            }

        async def content(self) -> str:
            return """
            <html>
              <body>
                <div class="product newsletter-card">
                  <a href="/products/hair-care/hair-care-accessories">Explore accessories</a>
                  <p>Subscribe to Dyson and get ₹2,000 off.</p>
                </div>
                <div class="product contact-card">
                  <a href="/contact">Contact us</a>
                  <p>You can call us 1-800-258-6688</p>
                </div>
              </body>
            </html>
            """

    count = await count_listing_cards(
        _WeakProductChromePage(),
        surface="ecommerce_listing",
    )

    assert count == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_prefers_product_anchor_count_over_productcard_substring() -> (
    None
):
    class _DesertcartCountPage:
        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            assert "querySelectorAll(selector).length" in script
            return {
                selector: (
                    10
                    if "productcard" in str(selector).lower()
                    else 4
                    if str(selector) == "a[href*='/products/']"
                    else 0
                )
                for selector in list(arg or [])
            }

    count = await count_listing_cards(
        _DesertcartCountPage(),
        surface="ecommerce_listing",
    )

    assert count == 4


@pytest.mark.asyncio
@pytest.mark.component
async def test_load_more_wait_keeps_best_delayed_card_gain() -> None:
    class _DelayedGainPage:
        def __init__(self) -> None:
            self.elapsed_ms = 0

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            self.elapsed_ms += int(timeout_ms)

        async def evaluate(self, script: str, arg: Any | None = None) -> Any:
            if "querySelectorAll(selector).length" in script:
                count = 236 if self.elapsed_ms >= 3000 else 144
                return {
                    selector: (count if str(selector) == "a[href*='/products/']" else 0)
                    for selector in list(arg or [])
                }
            return {
                "scroll_height": 2000,
                "client_height": 600,
                "overflow_containers": 0,
                "content_signature_source": f"cards-{self.elapsed_ms}",
            }

    snapshot = await wait_for_load_more_card_gain(
        _DelayedGainPage(),
        previous={"card_count": 144},
        surface="ecommerce_listing",
        max_records=200,
        deadline_at=None,
    )

    assert snapshot is not None
    assert snapshot["card_count"] == 236
