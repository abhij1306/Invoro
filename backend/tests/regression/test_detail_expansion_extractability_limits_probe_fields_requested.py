from __future__ import annotations

from .test_browser_expansion_runtime import *  # noqa: F403


@pytest.mark.regression
def test_detail_expansion_extractability_limits_probe_fields_to_requested() -> None:
    seen_probe_fields: set[str] | None = None

    def _fake_extractability(*_args, **kwargs):
        nonlocal seen_probe_fields
        raw_probe_fields = kwargs.get("probe_fields")
        seen_probe_fields = set(raw_probe_fields or [])
        return {
            "verified": True,
            "matched_requested_fields": ["materials"],
            "extractable_fields": ["materials"],
            "section_fields": ["materials"],
        }

    browser_page_helpers.detail_expansion_extractability(
        html="<html></html>",
        surface="ecommerce_detail",
        requested_fields=["materials"],
        requested_content_extractability_impl=_fake_extractability,
    )

    assert seen_probe_fields == {"materials"}

@pytest.mark.regression
def test_detail_expansion_extractability_uses_default_dom_probe_fields_without_requests() -> (
    None
):
    seen_probe_fields: set[str] | None = None

    def _fake_extractability(*_args, **kwargs):
        nonlocal seen_probe_fields
        raw_probe_fields = kwargs.get("probe_fields")
        seen_probe_fields = set(raw_probe_fields or [])
        return {
            "verified": False,
            "matched_requested_fields": [],
            "extractable_fields": [],
            "section_fields": [],
        }

    browser_page_helpers.detail_expansion_extractability(
        html="<html></html>",
        surface="ecommerce_detail",
        requested_fields=None,
        requested_content_extractability_impl=_fake_extractability,
    )

    assert seen_probe_fields is not None
    assert "description" in seen_probe_fields
    assert "materials" in seen_probe_fields

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_deadline_includes_page_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>"
    )
    captured_deadlines: list[float] = []
    perf_counter_calls = 0

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    def _perf_counter() -> float:
        nonlocal perf_counter_calls
        perf_counter_calls += 1
        return 100.0 if perf_counter_calls == 1 else 104.0

    def _remaining_timeout_factory(deadline: float):
        captured_deadlines.append(deadline)
        return lambda: 5.0

    monkeypatch.setattr(browser_runtime.time, "perf_counter", _perf_counter)
    monkeypatch.setattr(
        browser_runtime,
        "remaining_timeout_factory",
        _remaining_timeout_factory,
    )

    await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert captured_deadlines == [105.0]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_fast_paths_ready_detail_without_extra_waits() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html>
          <head>
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Product","name":"Widget Prime"}
            </script>
          </head>
          <body>
            <h1>Widget Prime</h1>
            <div>
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
              Detailed product information with visible rendered content.
            </div>
          </body>
        </html>
        """,
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

    assert result.browser_diagnostics["phase_timings_ms"]["optimistic_wait"] == 0
    assert result.browser_diagnostics["phase_timings_ms"]["networkidle_wait"] == 0
    assert result.browser_diagnostics["phase_timings_ms"]["readiness_wait"] == 0
    assert result.browser_diagnostics["networkidle_skip_reason"] == "fast_path_ready"
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"]
        == "canonical_detail_already_ready"
    )
    assert result.browser_diagnostics["detail_expansion"]["status"] == "skipped"
    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 0
    assert page.goto_calls == ["domcontentloaded"]
    assert page.wait_timeout_calls == []
    assert page.content_calls == 2
    assert "networkidle" not in page.load_state_calls

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_closes_unexpected_popup_pages() -> None:
    popup_page = _FakeExpansionPage(base_html="<html><body>popup</body></html>")

    class _PopupPage(_FakeExpansionPage):
        async def goto(
            self,
            url: str,
            wait_until: str | None = None,
            **kwargs,
        ) -> Any:
            response = await super().goto(url, wait_until=wait_until, **kwargs)
            for callback in tuple(self.listeners.get("context:page", [])):
                callback(popup_page)
            await asyncio.sleep(0)
            return response

    page = _PopupPage(
        base_html="""
        <html>
          <head>
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Product","name":"Widget Prime"}
            </script>
          </head>
          <body>
            <h1>Widget Prime</h1>
            <p>Price Reviews Product details Shipping</p>
          </body>
        </html>
        """,
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

    assert result.browser_diagnostics["browser_outcome"] == "usable_content"
    assert popup_page.page_close_calls == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_recovers_direct_navigation_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A transient (non-terminal) challenge shell: no "Access Denied" title/strong
    # evidence, so it is NOT a terminal hard block and the recovery loop must keep
    # polling until the shell swaps to usable content (INVARIANTS §6).
    page = _FakeExpansionPage(
        base_html="<html><head><title>Just a moment...</title></head><body><div id='challenge'>Verifying your browser...</div></body></html>",
        wait_html_sequence=[
            """
            <html>
              <head>
                <script type="application/ld+json">
                {"@context":"https://schema.org","@type":"Product","name":"Widget Prime","offers":{"price":"12.00"}}
                </script>
              </head>
              <body>
                <main>
                  <h1>Widget Prime</h1>
                  <img src="/widget.jpg" alt="Widget Prime">
                  <span class="price">$12.00</span>
                  <button>Add to cart</button>
                  <p>Durable product description with enough visible detail for extraction.</p>
                </main>
              </body>
            </html>
            """
        ],
        goto_status=403,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _classify_blocked_page(html: str, status_code: int):
        await _async_checkpoint()
        lowered = html.lower()
        challenged = "verifying your browser" in lowered or "just a moment" in lowered
        return SimpleNamespace(
            blocked=challenged,
            evidence=["provider:datadome"] if challenged else [],
            provider_hits=["datadome"] if challenged else [],
            active_provider_hits=["datadome"] if challenged else [],
            title_matches=[],
            strong_hits=[],
            challenge_element_hits=["#challenge"] if challenged else [],
        )

    monkeypatch.setattr(
        browser_runtime,
        "classify_blocked_page_async",
        _classify_blocked_page,
    )
    monkeypatch.setattr(
        browser_page_flow,
        "classify_blocked_page_async",
        _classify_blocked_page,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        browser_reason="http-escalation",
        runtime_provider=_fake_runtime,
    )

    assert result.status_code == 200
    assert result.browser_diagnostics["browser_outcome"] == "usable_content"
    assert "Widget Prime" in result.html
    assert page.wait_timeout_calls

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_does_not_repeat_challenge_recovery_after_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        browser_runtime.crawler_runtime_settings,
        "origin_warm_pause_ms",
        0,
    )
    page = _FakeExpansionPage(
        base_html="<html><head><title>Access Denied</title></head><body>Access Denied</body></html>",
        goto_status=403,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    recover_calls: list[str] = []

    async def _recover_once(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        recover_calls.append("recover")
        return SimpleNamespace(status=403, headers={"content-type": "text/html"})

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(
            blocked=True,
            evidence=["title:access denied"],
            provider_hits=[],
            challenge_element_hits=[],
        )

    monkeypatch.setattr(browser_page_flow, "recover_browser_challenge", _recover_once)
    monkeypatch.setattr(browser_runtime, "recover_browser_challenge", _recover_once)
    monkeypatch.setattr(
        browser_runtime,
        "classify_blocked_page_async",
        _classify_blocked_page,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert recover_calls == ["recover"]
    assert result.status_code == 403
    assert result.browser_diagnostics["browser_outcome"] == "challenge_page"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_fast_paths_ready_listing_cards_without_networkidle() -> (
    None
):
    selectors = list(CARD_SELECTORS.get("ecommerce") or [])
    page = _FakeExpansionPage(
        base_html="<html><body><article class='product-card'>A</article></body></html>",
        selector_counts=dict.fromkeys(selectors[:1], 3),
        card_count=3,
    )
    page.card_selectors = set(selectors)

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert result.browser_diagnostics["phase_timings_ms"]["networkidle_wait"] == 0
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"] == "non_detail_surface"
    )
    assert page.wait_timeout_calls == []
    assert page.load_state_calls == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_listing_does_not_treat_product_titles_as_extractable_fields() -> (
    None
):
    selectors = list(CARD_SELECTORS.get("ecommerce") or [])
    page = _FakeExpansionPage(
        base_html="""
        <html>
          <body>
            <section class="product-card-grid">
              <article class="product-card">
                <h2>Batman Wayne Industries</h2>
                <p>Relaxed fit cotton shirt with oversized graphic print.</p>
              </article>
              <article class="product-card">
                <h2>Venom Pure Destruction</h2>
                <p>Heavyweight jersey shirt with all-over print.</p>
              </article>
            </section>
          </body>
        </html>
        """,
        selector_counts=dict.fromkeys(selectors[:1], 2),
        card_count=2,
    )
    page.card_selectors = set(selectors)

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert (
        result.browser_diagnostics["detail_expansion"]["reason"] == "non_detail_surface"
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_listing_skips_detail_extractability_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selectors = list(CARD_SELECTORS.get("ecommerce") or [])
    page = _FakeExpansionPage(
        base_html="<html><body><article class='product-card'>A</article></body></html>",
        selector_counts=dict.fromkeys(selectors[:1], 3),
        card_count=3,
    )
    page.card_selectors = set(selectors)

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert (
        result.browser_diagnostics["detail_expansion"]["reason"] == "non_detail_surface"
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_attempts_implicit_networkidle_for_unmatched_spa_listing(
    patch_settings,
) -> None:
    patch_settings(
        browser_navigation_optimistic_wait_ms=25,
        browser_spa_implicit_networkidle_timeout_ms=250,
    )
    page = _FakeExpansionPage(base_html="<html><body>Loading</body></html>")
    probe_results = iter(
        [
            {
                "url": "https://example.com/spa/listing",
                "surface": "ecommerce_listing",
                "is_ready": False,
                "detail_like": False,
                "structured_data_present": True,
                "visible_text_length": 20,
                "detail_hint_count": 0,
                "listing_card_count": 0,
                "matched_listing_selectors": 0,
                "h1_present": False,
            },
            {
                "url": "https://example.com/spa/listing",
                "surface": "ecommerce_listing",
                "is_ready": False,
                "detail_like": False,
                "structured_data_present": True,
                "visible_text_length": 24,
                "detail_hint_count": 0,
                "listing_card_count": 0,
                "matched_listing_selectors": 0,
                "h1_present": False,
            },
            {
                "url": "https://example.com/spa/listing",
                "surface": "ecommerce_listing",
                "is_ready": False,
                "detail_like": False,
                "structured_data_present": True,
                "visible_text_length": 260,
                "detail_hint_count": 0,
                "listing_card_count": 0,
                "matched_listing_selectors": 0,
                "h1_present": False,
            },
            {
                "url": "https://example.com/spa/listing",
                "surface": "ecommerce_listing",
                "is_ready": False,
                "detail_like": False,
                "structured_data_present": True,
                "visible_text_length": 260,
                "detail_hint_count": 0,
                "listing_card_count": 0,
                "matched_listing_selectors": 0,
                "h1_present": False,
            },
        ]
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    original_probe_browser_readiness = browser_runtime.probe_browser_readiness
    try:

        async def _fake_probe_browser_readiness(*args, **kwargs):
            await _async_checkpoint()
            del args, kwargs
            try:
                return probe_results.__next__()
            except StopIteration as exc:
                raise AssertionError("Expected another probe result") from exc

        browser_runtime.probe_browser_readiness = _fake_probe_browser_readiness
        result = await browser_runtime.browser_fetch(
            "https://example.com/spa/listing",
            5,
            surface="ecommerce_listing",
            runtime_provider=_fake_runtime,
        )
    finally:
        browser_runtime.probe_browser_readiness = original_probe_browser_readiness

    assert result.browser_diagnostics["phase_timings_ms"]["optimistic_wait"] >= 0
    assert result.browser_diagnostics["phase_timings_ms"]["networkidle_wait"] >= 0
    assert result.browser_diagnostics["phase_timings_ms"]["readiness_wait"] >= 0
    assert page.wait_timeout_calls == []
    assert page.wait_function_calls == [25]
    assert page.load_state_calls == ["networkidle"]
    assert result.browser_diagnostics["networkidle_skip_reason"] is None

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_does_not_fast_path_listing_on_visible_text_alone() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body>" + ("Catalog entry " * 40) + "</body></html>",
    )

    probe = await browser_runtime.probe_browser_readiness(
        page,
        url="https://example.com/catalog",
        surface="ecommerce_listing",
        listing_override=None,
    )

    assert probe["listing_card_count"] == 0
    assert probe["matched_listing_selectors"] == 0
    assert probe["visible_text_length"] >= (
        int(crawler_runtime_settings.browser_readiness_visible_text_min) * 2
    )
    assert probe["is_ready"] is False

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_does_not_fast_path_ecommerce_category_cards() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <h1>Outdoor Footwear</h1>
          <button class="plp-card">
            <a href="/ca/en/c/mens/footwear-run/wid-kjyr4dq9">
              <h4>Run footwear</h4>
              <img src="/run.jpg" alt="Trail running category">
            </a>
          </button>
          <button class="plp-card">
            <a href="/ca/en/c/mens/footwear-hike/wid-kjyr4dq9">
              <h4>Hike footwear</h4>
              <img src="/hike.jpg" alt="Hike category">
            </a>
          </button>
          <button class="plp-card">
            <a href="/ca/en/c/mens/footwear-climb/wid-kjyr4dq9">
              <h4>Climb footwear</h4>
              <img src="/climb.jpg" alt="Climb category">
            </a>
          </button>
        </body></html>
        """,
        selector_counts={".plp-card": 3},
    )

    probe = await browser_runtime.probe_browser_readiness(
        page,
        url="https://arcteryx.com/ca/en/c/mens/footwear",
        surface="ecommerce_listing",
        listing_override=None,
    )

    assert probe["listing_card_count"] == 0
    assert probe["is_ready"] is False

@pytest.mark.regression
def test_ecommerce_ready_card_count_rejects_repeated_product_attribute_tokens() -> None:
    soup = BeautifulSoup(
        """
        <html><body>
          <div class="product-card-card">
            <a href="/collections/run"><img src="/run.jpg" alt="Run"></a>
          </div>
          <div class="product-card-card">
            <a href="/collections/hike"><img src="/hike.jpg" alt="Hike"></a>
          </div>
          <div class="product-card-card">
            <a href="/collections/climb"><img src="/climb.jpg" alt="Climb"></a>
          </div>
        </body></html>
        """,
        "html.parser",
    )

    assert browser_readiness._ecommerce_ready_card_count(soup) == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_accepts_ecommerce_product_tiles() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <div class="qa--grid-product-tile product-tile" data-product-id="X000009613">
            <a href="/shop/mens/vertex-speed-shoe-9613">
              <img src="/vertex.jpg" alt="Vertex Speed Shoe Men's">
              <span class="product-tile-name">Vertex Speed Shoe Men's</span>
              <span class="product-tile-price">$240.00</span>
            </a>
          </div>
          <div class="qa--grid-product-tile product-tile" data-product-id="X000009715">
            <a href="/shop/mens/vertex-speed-low-shoe-9715">
              <img src="/vertex-low.jpg" alt="Vertex Speed Low Shoe Men's">
              <span class="product-tile-name">Vertex Speed Low Shoe Men's</span>
              <span class="product-tile-price">$230.00</span>
            </a>
          </div>
          <div class="qa--grid-product-tile product-tile" data-product-id="X000010398">
            <a href="/shop/mens/norvan-ld-4-shoe-0398">
              <img src="/norvan.jpg" alt="Norvan LD 4 Shoe Men's">
              <span class="product-tile-name">Norvan LD 4 Shoe Men's</span>
              <span class="product-tile-price">$220.00</span>
            </a>
          </div>
        </body></html>
        """,
    )

    probe = await browser_runtime.probe_browser_readiness(
        page,
        url="https://arcteryx.com/ca/en/c/mens/footwear",
        surface="ecommerce_listing",
        listing_override=None,
    )

    assert probe["listing_card_count"] == 3
    assert probe["is_ready"] is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_fast_paths_h1_detail_without_configured_hints() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html>
          <head><title>Widget Prime for Men | Example</title></head>
          <body>
            <h1>Widget Prime</h1>
            <p>
              Premium polarized sunglasses with silver-tone aviator frames,
              adjustable nose pads, and a protective case included for everyday wear.
            </p>
            <span>$450.00</span>
          </body>
        </html>
        """,
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

    assert result.browser_diagnostics["readiness_probes"][0]["is_ready"] is True
    assert result.browser_diagnostics["phase_timings_ms"]["optimistic_wait"] == 0
    assert result.browser_diagnostics["phase_timings_ms"]["networkidle_wait"] == 0
    assert result.browser_diagnostics["phase_timings_ms"]["readiness_wait"] == 0
    assert result.browser_diagnostics["detail_expansion"]["status"] == "skipped"
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"]
        == "canonical_detail_already_ready"
    )
    assert page.wait_function_calls == []
    assert page.load_state_calls == []
    assert page.wait_timeout_calls == []
