from __future__ import annotations

from .test_traversal_runtime import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.component
async def test_count_listing_cards_heuristic_rejects_detail_sections_with_support_links(
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
                <main>
                  <section class="product-details">
                    <h2>Shipping information</h2>
                    <p>Read the delivery policy and returns process for this product.</p>
                    <a href="/shipping">Shipping policy</a>
                  </section>
                  <section class="product-details">
                    <h2>Warranty</h2>
                    <p>Find the product warranty terms and support instructions here.</p>
                    <a href="/support/warranty">Warranty terms</a>
                  </section>
                  <section class="product-details">
                    <h2>Care guide</h2>
                    <p>Learn how to clean and maintain the product after purchase.</p>
                    <a href="/support/care">Care guide</a>
                  </section>
                </main>
              </body>
            </html>
            """

    monkeypatch.setattr(
        "app.services.acquisition.traversal_card_counting.CARD_SELECTORS",
        {"ecommerce": [".product-card"], "jobs": [".job-card"]},
    )

    count = await count_listing_cards(_SelectorPage(), surface="ecommerce_listing")

    assert count == 0

@pytest.mark.asyncio
async def testclick_with_retry_uses_mutation_settle_after_js_fallback() -> None:
    class _ClickPage:
        def __init__(self) -> None:
            self.load_state_calls: list[str] = []
            self.wait_timeout_calls: list[int] = []
            self.mutation_settle_calls = 0

        def locator(self, selector: str):
            del selector
            return _OverlayCookieLocator()

        async def evaluate(self, script: str, arg: Any | None = None) -> Any:
            del arg
            if "MutationObserver" in script:
                self.mutation_settle_calls += 1
                return {"observed": True}
            return None

        async def wait_for_load_state(
            self,
            state: str,
            timeout: int | None = None,
        ) -> None:
            self.load_state_calls.append(state)

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            self.wait_timeout_calls.append(timeout_ms)

    class _ClickLocator:
        async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
            return None

        async def evaluate(self, script: str) -> Any:
            if "scrollIntoView" in script:
                return None
            if "node.click()" in script:
                return None
            return 0

        async def click(self, timeout: int | None = None, force: bool = False) -> None:
            del timeout, force
            raise traversal_module.PlaywrightError("intercepted")

    page = _ClickPage()
    locator = _ClickLocator()
    result = TraversalResult(requested_mode="load_more")

    clicked = await click_with_retry(page, locator, result=result)

    assert clicked is True
    assert result.click_retries == 2
    assert page.mutation_settle_calls == 1
    assert page.wait_timeout_calls == []

@pytest.mark.asyncio
async def testclick_with_retry_stops_when_locator_no_longer_resolves() -> None:
    class _ClickPage:
        url = "https://example.com/listing"

        def locator(self, selector: str):
            del selector
            return _OverlayCookieLocator()

        async def evaluate(self, script: str, arg: Any | None = None) -> Any:
            del script, arg
            return None

        async def wait_for_load_state(
            self,
            state: str,
            timeout: int | None = None,
        ) -> None:
            return None

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            return None

    class _StaleLocator:
        def __init__(self) -> None:
            self.detached = False
            self.click_calls = 0

        async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
            return None

        async def evaluate(self, script: str) -> Any:
            del script
            self.detached = True
            raise traversal_module.PlaywrightError("detached")

        async def count(self) -> int:
            return 0 if self.detached else 1

        async def click(self, timeout: int | None = None, force: bool = False) -> None:
            del timeout, force
            self.click_calls += 1
            raise AssertionError("click should not run once locator is stale")

    page = _ClickPage()
    locator = _StaleLocator()
    result = TraversalResult(requested_mode="load_more")

    clicked = await click_with_retry(page, locator, result=result)

    assert clicked is False
    assert locator.click_calls == 0
    assert result.click_retries == 0

@pytest.mark.asyncio
async def testclick_with_retry_tolerates_transient_locator_resolution_loss() -> None:
    class _ClickPage:
        url = "https://example.com/listing"

        def locator(self, selector: str):
            del selector
            return _OverlayCookieLocator()

        async def evaluate(self, script: str, arg: Any | None = None) -> Any:
            del script, arg
            return None

        async def wait_for_load_state(
            self,
            state: str,
            timeout: int | None = None,
        ) -> None:
            return None

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            return None

    class _TransientLocator:
        def __init__(self) -> None:
            self.count_calls = 0
            self.click_calls = 0

        async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
            return None

        async def evaluate(self, script: str) -> Any:
            del script
            raise traversal_module.PlaywrightError("transient evaluate failure")

        async def count(self) -> int:
            self.count_calls += 1
            return 0 if self.count_calls == 1 else 1

        async def click(self, timeout: int | None = None, force: bool = False) -> None:
            del timeout, force
            self.click_calls += 1
            return None

    page = _ClickPage()
    locator = _TransientLocator()
    result = TraversalResult(requested_mode="load_more")

    clicked = await click_with_retry(page, locator, result=result)

    assert clicked is True
    assert locator.click_calls == 1

@pytest.mark.asyncio
async def testlocator_still_resolves_returns_false_after_probe_errors() -> None:
    class _ProbeErrorLocator:
        async def count(self) -> int:
            raise traversal_module.PlaywrightError("transient probe failure")

    assert await locator_still_resolves(_ProbeErrorLocator()) is False

@pytest.mark.asyncio
async def testclick_with_retry_tolerates_locator_probe_errors() -> None:
    class _ClickPage:
        url = "https://example.com/listing"

        def locator(self, selector: str):
            del selector
            return _OverlayCookieLocator()

        async def evaluate(self, script: str, arg: Any | None = None) -> Any:
            del script, arg
            return None

        async def wait_for_load_state(
            self,
            state: str,
            timeout: int | None = None,
        ) -> None:
            return None

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            return None

    class _ProbeErrorLocator:
        def __init__(self) -> None:
            self.click_calls = 0

        async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
            return None

        async def evaluate(self, script: str) -> Any:
            del script
            return None

        async def count(self) -> int:
            raise traversal_module.PlaywrightError("transient probe failure")

        async def click(self, timeout: int | None = None, force: bool = False) -> None:
            del timeout, force
            self.click_calls += 1
            return None

    page = _ClickPage()
    locator = _ProbeErrorLocator()
    result = TraversalResult(requested_mode="load_more")

    clicked = await click_with_retry(page, locator, result=result)

    assert clicked is True
    assert locator.click_calls == 1
