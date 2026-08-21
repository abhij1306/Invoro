from __future__ import annotations

from .test_traversal_runtime import PAGINATION_SELECTORS, _FakePage, _State, execute_listing_traversal, listing_node_html, pytest, traversal_module  # fmt: skip

@pytest.mark.component
def test_listing_node_html_suppresses_unexpected_parser_errors(caplog) -> None:
    class _BrokenNode:
        @property
        def html(self) -> str:
            raise RuntimeError("parser failed")

    assert listing_node_html(_BrokenNode()) == ""
    assert "Failed to read listing node HTML fragment" in caplog.text

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_collects_multiple_pages() -> None:
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
            _State(
                html="<div>page-2</div>",
                card_count=5,
                scroll_height=1400,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=3,
        max_scrolls=2,
    )

    assert result.selected_mode == "paginate"
    assert result.pages_advanced == 1
    assert result.progress_events == 1
    fragments = [fragment for fragment, _ in result.html_fragments]
    assert "page-1" in "\n".join(fragments)
    assert "page-2" in "\n".join(fragments)

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_does_not_append_duplicate_html_without_progress() -> (
    None
):
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1200,
            controls={"next_page"},
        ),
        paginated_states=[
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=1200,
                controls={"next_page"},
            ),
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=1200,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.stop_reason == "paginate_no_progress"
    assert [f for f, _ in result.html_fragments] == ["<div>page-1</div>"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_stops_when_card_count_stays_zero() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1 chrome</div>",
            card_count=0,
            scroll_height=1200,
            controls={"next_page"},
            next_href="https://example.com/listing?page=2",
        ),
        paginated_states=[
            _State(
                html="<div>page-1 chrome</div>",
                card_count=0,
                scroll_height=1200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=2",
            ),
            _State(
                html="<div>page-2 different chrome</div>",
                card_count=0,
                scroll_height=1200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=3",
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=3,
        max_scrolls=1,
    )

    assert result.stop_reason == "paginate_no_progress"
    assert result.progress_events == 0
    assert result.pages_advanced == 0

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_settles_thin_initial_listing_before_stopping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settled_state = _State(
        html="<html><body>"
        + "".join(
            f"<article class='product-card'><a href='/products/widget-{index}'>Widget {index}</a><span>$10</span></article>"
            for index in range(8)
        )
        + "</body></html>",
        card_count=8,
        scroll_height=2200,
    )
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<html><body><section><a href='/promo'>Promo</a><span>$10</span></section></body></html>",
            card_count=5,
            scroll_height=900,
        ),
    )

    async def _settle(page_arg, **kwargs):
        del kwargs
        page_arg.state = settled_state

    monkeypatch.setattr(traversal_module, "_settle_after_action", _settle)

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=3,
        max_scrolls=1,
    )

    assert result.progress_events == 1
    assert result.card_count == 8
    assert "Widget 7" in result.compose_html()

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_blocks_off_domain_links() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1200,
            controls={"next_page"},
            next_href="https://ads.example.net/promo",
        ),
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.stop_reason == "paginate_off_domain"
    assert [f for f, _ in result.html_fragments] == ["<div>page-1</div>"]
    assert page.goto_calls == []

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_logs_explicit_stop_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1200,
            controls={"next_page"},
            next_href="https://ads.example.net/promo",
        ),
    )

    with caplog.at_level("INFO"):
        result = await execute_listing_traversal(
            page,
            surface="ecommerce_listing",
            traversal_mode="paginate",
            max_pages=2,
            max_scrolls=1,
        )

    assert result.stop_reason == "paginate_off_domain"
    assert "stop_reason=paginate_off_domain" in caplog.text

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_waits_for_navigation_transition() -> None:
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
            _State(
                html="<div>page-2</div>",
                card_count=4,
                scroll_height=1500,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.pages_advanced == 1
    assert "domcontentloaded" in page.load_state_calls
    assert "networkidle" in page.load_state_calls

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_handles_spa_next_button() -> None:
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

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=2,
    )

    assert result.selected_mode == "paginate"
    assert result.pages_advanced == 1
    assert result.progress_events == 1
    assert [f for f, _ in result.html_fragments] == [
        "<div>page-1</div>",
        "<div>page-2</div>",
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_handles_numeric_arrow_button() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1800,
            client_height=600,
            controls={"next_page"},
            next_href="https://example.com/listing?page=2",
            next_control_state={
                "raw_href": "https://example.com/listing?page=2",
                "has_click_handler": False,
                "pagination_container": True,
                "pagination_text": False,
                "sibling_page_numbers": True,
                "follows_current_page": True,
                "arrow_only": True,
                "is_button_like": True,
            },
        ),
        paginated_states=[
            _State(
                html="<div>page-1</div>",
                card_count=2,
                scroll_height=1800,
                client_height=600,
                controls={"next_page"},
                next_href="https://example.com/listing?page=2",
                next_control_state={
                    "raw_href": "https://example.com/listing?page=2",
                    "has_click_handler": False,
                    "pagination_container": True,
                    "pagination_text": False,
                    "sibling_page_numbers": True,
                    "follows_current_page": True,
                    "arrow_only": True,
                    "is_button_like": True,
                },
            ),
            _State(
                html="<div>page-2</div>",
                card_count=5,
                scroll_height=2100,
                client_height=600,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=2,
    )

    assert result.selected_mode == "paginate"
    assert result.pages_advanced == 1
    assert result.progress_events == 1

@pytest.mark.asyncio
@pytest.mark.component
async def test_looks_like_paginate_control_rejects_plain_href_without_pagination_signals() -> (
    None
):
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=2,
            scroll_height=1800,
            controls={"next_page"},
            next_href="https://example.com/products/widget",
            next_control_state={
                "raw_href": "https://example.com/products/widget",
                "has_click_handler": False,
                "pagination_container": False,
                "pagination_text": False,
                "sibling_page_numbers": False,
                "follows_current_page": False,
                "arrow_only": False,
                "is_button_like": False,
            },
        ),
    )

    locator = page.locator(PAGINATION_SELECTORS["next_page"][0]).first

    assert await traversal_module.looks_like_paginate_control(locator) is False

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_traversal_stops_before_recording_block_challenge() -> None:
    challenge_html = """
    <html>
      <head><title>Just a moment...</title></head>
      <body>
        <main>Checking your browser before accessing Cloudflare protected content.</main>
        <div id="cf-challenge-running">Just a moment...</div>
      </body>
    </html>
    """
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
            _State(
                html=challenge_html,
                card_count=0,
                scroll_height=900,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=2,
        max_scrolls=1,
    )

    assert result.stop_reason == "paginate_blocked"
    assert result.pages_advanced == 0
    assert result.progress_events == 0
    assert [f for f, _ in result.html_fragments] == ["<div>page-1</div>"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_load_more_traversal_runs_when_button_present() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>before</div>",
            card_count=2,
            scroll_height=900,
            controls={"load_more"},
        ),
        load_more_states=[
            _State(
                html="<div>before</div>",
                card_count=2,
                scroll_height=900,
                controls={"load_more"},
            ),
            _State(
                html="<div>after</div>",
                card_count=5,
                scroll_height=1200,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="load_more",
        max_pages=2,
        max_scrolls=2,
    )

    assert result.selected_mode == "load_more"
    assert result.load_more_clicks == 1
    assert result.progress_events == 1
    assert result.card_count == 5
    assert [f for f, _ in result.html_fragments] == [
        "<div>before</div>",
        "<div>after</div>",
    ]
    assert "networkidle" in page.load_state_calls

@pytest.mark.asyncio
@pytest.mark.component
async def test_load_more_traversal_stops_at_user_max_records() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>before</div>",
            card_count=2,
            scroll_height=900,
            controls={"load_more"},
        ),
        load_more_states=[
            _State(
                html="<div>before</div>",
                card_count=2,
                scroll_height=900,
                controls={"load_more"},
            ),
            _State(
                html="<div>after</div>",
                card_count=5,
                scroll_height=1200,
                controls={"load_more"},
            ),
            _State(
                html="<div>too-far</div>",
                card_count=9,
                scroll_height=1500,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="load_more",
        max_pages=3,
        max_scrolls=2,
        max_records=5,
    )

    assert result.stop_reason == "target_records_reached"
    assert result.load_more_clicks == 1
    assert result.card_count == 5
    assert [f for f, _ in result.html_fragments] == [
        "<div>before</div>",
        "<div>after</div>",
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_load_more_target_uses_unique_card_identities_not_repeated_snapshots() -> (
    None
):
    first_html = (
        "<main>"
        "<article class='product-card'><a href='/products/widget-1'>Widget 1</a><span>$10</span></article>"
        "<article class='product-card'><a href='/products/widget-2'>Widget 2</a><span>$20</span></article>"
        "</main>"
    )
    repeated_html = (
        "<main>"
        "<article class='product-card'><a href='/products/widget-1'>Widget 1</a><span>$10</span></article>"
        "<article class='product-card'><a href='/products/widget-2'>Widget 2</a><span>$20</span></article>"
        "<article class='product-card'><a href='/products/widget-1'>Widget 1</a><span>$10</span></article>"
        "<article class='product-card'><a href='/products/widget-2'>Widget 2</a><span>$20</span></article>"
        "</main>"
    )
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html=first_html,
            card_count=4,
            scroll_height=900,
            controls={"load_more"},
        ),
        load_more_states=[
            _State(
                html=first_html, card_count=4, scroll_height=900, controls={"load_more"}
            ),
            _State(
                html=repeated_html, card_count=8, scroll_height=1200, controls=set()
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="load_more",
        max_pages=3,
        max_scrolls=2,
        max_records=3,
    )

    assert result.stop_reason != "target_records_reached"
    assert result.card_count == 2

@pytest.mark.asyncio
@pytest.mark.component
async def test_paginate_uses_max_records_as_page_stop_not_page_limit() -> None:
    page = _FakePage(
        surface="ecommerce_listing",
        initial_state=_State(
            html="<div>page-1</div>",
            card_count=80,
            scroll_height=1200,
            controls={"next_page"},
            next_href="https://example.com/listing?page=2",
        ),
        paginated_states=[
            _State(
                html="<div>page-1</div>",
                card_count=80,
                scroll_height=1200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=2",
            ),
            _State(
                html="<div>page-2</div>",
                card_count=80,
                scroll_height=2200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=3",
            ),
            _State(
                html="<div>page-3</div>",
                card_count=80,
                scroll_height=3200,
                controls={"next_page"},
                next_href="https://example.com/listing?page=4",
            ),
            _State(
                html="<div>page-4</div>",
                card_count=80,
                scroll_height=4200,
                controls=set(),
            ),
        ],
    )

    result = await execute_listing_traversal(
        page,
        surface="ecommerce_listing",
        traversal_mode="paginate",
        max_pages=1,
        max_scrolls=1,
        max_records=200,
    )

    assert result.stop_reason == "target_records_reached"
    assert result.pages_advanced == 2
    assert result.card_count == 240
    assert [f for f, _ in result.html_fragments] == [
        "<div>page-1</div>",
        "<div>page-2</div>",
        "<div>page-3</div>",
    ]
