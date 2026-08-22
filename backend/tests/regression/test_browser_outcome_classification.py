from __future__ import annotations

from .test_browser_expansion_runtime import TraversalResult, browser_runtime, pytest  # fmt: skip


@pytest.mark.regression
def test_classify_browser_outcome_marks_empty_category_as_low_content_shell() -> None:
    html = "<html><body><h1>Empty category</h1></body></html>"

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )


@pytest.mark.regression
def test_classify_browser_outcome_marks_site_maintenance_title_as_low_content_shell() -> (
    None
):
    html = """
    <html>
      <head><title>Site Maintenance</title></head>
      <body>
        <main>
          <h1>Site Maintenance</h1>
          <p>
            We're making a few updates to our site and working through a short
            maintenance window so shopping is unavailable right now, but we will
            be back shortly with full product access.
          </p>
        </main>
      </body>
    </html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )


@pytest.mark.regression
def test_classify_browser_outcome_marks_error_page_title_as_low_content_shell() -> None:
    html = """
    <html>
      <head><title>Error Page</title></head>
      <body>
        <main>
          <h1>Error Page</h1>
          <p>
            The requested page cannot be displayed right now. Please try again
            later or return to the previous page.
          </p>
        </main>
      </body>
    </html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )


@pytest.mark.regression
def test_classify_low_content_reason_ignores_empty_phrase_on_contentful_page() -> None:
    html = """
    <html><body>
      <p>Filter summary: 0 results for XXL.</p>
      <article><a href="/products/widget-1">Widget One</a><span>$10</span></article>
      <article><a href="/products/widget-2">Widget Two</a><span>$20</span></article>
      <article><a href="/products/widget-3">Widget Three</a><span>$30</span></article>
      <article><a href="/products/widget-4">Widget Four</a><span>$40</span></article>
      <article><a href="/products/widget-5">Widget Five</a><span>$50</span></article>
    </body></html>
    """

    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        is None
    )


@pytest.mark.regression
def test_classify_browser_outcome_keeps_ready_listing_with_no_pagination_progress_usable() -> (
    None
):
    html = """
    <html><body>
      <article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>
      <article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>
      <article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>
    </body></html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
        traversal_result=TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="next_page_not_found",
            progress_events=0,
            card_count=3,
        ),
    )

    assert outcome == "usable_content"


@pytest.mark.regression
def test_classify_browser_outcome_keeps_extractable_listing_usable_below_threshold() -> (
    None
):
    html = """
    <html><body>
      <article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>
      <article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>
      <article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>
    </body></html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
        traversal_result=TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="paginate_no_progress",
            progress_events=0,
            card_count=0,
        ),
    )

    assert outcome == "usable_content"


@pytest.mark.regression
def test_build_failed_browser_diagnostics_marks_page_closed_explicitly() -> None:
    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=RuntimeError("Target closed"),
    )

    assert diagnostics["browser_outcome"] == "navigation_failed"
    assert diagnostics["failure_kind"] == "page_closed"
    assert diagnostics["failure_stage"] == "navigation"
