from __future__ import annotations

import pytest

from app.services.acquisition import browser_readiness
from app.services.dom.html_parser import BeautifulSoup


@pytest.mark.regression
def test_ready_card_count_uses_dom_identity_for_identical_cards() -> None:
    soup = BeautifulSoup(
        """
        <html><body>
          <article class="product-card" data-product-id="1">
            <a href="/products/widget">Widget</a><span>$10.00</span>
          </article>
          <article class="product-card" data-product-id="1">
            <a href="/products/widget">Widget</a><span>$10.00</span>
          </article>
        </body></html>
        """,
        "html.parser",
    )

    assert browser_readiness._ecommerce_ready_card_count(soup) == 2
