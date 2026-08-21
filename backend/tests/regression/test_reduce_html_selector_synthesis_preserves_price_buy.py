from __future__ import annotations

from .test_detail_extractor_priority_and_selector_self_heal import Path, extract_records, load_export_data, pytest, reduce_html_for_selector_synthesis, selector_heal_improved_record, validated_xpath_rules  # fmt: skip

@pytest.mark.regression
def test_reduce_html_for_selector_synthesis_preserves_price_and_buy_box_controls() -> (
    None
):
    reduced = reduce_html_for_selector_synthesis(
        """
        <html><body>
          <main>
            <form class="buy-box" data-product-id="sku-1">
              <span class="price" data-price="229.99" itemprop="price">$229.99</span>
              <button type="button" aria-label="Size 9" data-variant-id="v9">9</button>
              <input name="sku" data-sku="sku-1" value="sku-1" />
            </form>
          </main>
        </body></html>
        """
    )

    assert 'data-price="229.99"' in reduced
    assert 'itemprop="price"' in reduced
    assert 'aria-label="Size 9"' in reduced
    assert 'data-variant-id="v9"' in reduced
    assert 'data-sku="sku-1"' in reduced
    assert 'value="sku-1"' in reduced

@pytest.mark.regression
def test_selector_synthesis_keep_worthy_tags_are_code_owned() -> None:
    from app.services.config.selectors import SELECTOR_SYNTHESIS_KEEP_WORTHY_TAGS

    exports = load_export_data(
        str(
            Path(__file__).parents[2]
            / "app"
            / "services"
            / "config"
            / "selectors.exports.json"
        )
    )

    assert "SELECTOR_SYNTHESIS_KEEP_WORTHY_TAGS" not in exports
    assert SELECTOR_SYNTHESIS_KEEP_WORTHY_TAGS == frozenset(
        {"button", "input", "select"}
    )

@pytest.mark.regression
def test_extract_records_deep_merges_structured_variant_fields_across_tiers() -> None:
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <label>
          Color
          <select name="color">
            <option value="">Choose color</option>
            <option value="black">Black</option>
            <option value="olive">Olive</option>
          </select>
        </label>
      </body>
    </html>
    """

    extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variant_axes", "selected_variant"],
        adapter_records=[
            {
                "variant_axes": {"size": ["S", "M"]},
                "selected_variant": {
                    "sku": "TRAIL-S",
                    "option_values": {"size": "S"},
                },
            }
        ],
    )[0]

@pytest.mark.regression
def test_selector_self_heal_requires_field_level_improvement_before_persisting() -> (
    None
):
    assert (
        selector_heal_improved_record(
            before_record={"title": "Widget Prime", "price": ""},
            after_record={"title": "Widget Prime", "price": "19.99"},
            target_fields=["price"],
        )
        is True
    )
    assert (
        selector_heal_improved_record(
            before_record={"title": "Widget Prime", "price": ""},
            after_record={"title": "Widget Prime", "price": ""},
            target_fields=["price"],
        )
        is False
    )

@pytest.mark.regression
def test_selector_self_heal_converts_css_candidates_before_persisting_xpath() -> None:
    rules = validated_xpath_rules(
        html="""
        <html>
          <body>
            <div class="custom-specs">Rubber outsole, reinforced toe cap.</div>
          </body>
        </html>
        """,
        candidates=[
            {
                "field_name": "specifications",
                "xpath": "div.custom-specs",
            }
        ],
        target_fields=["specifications"],
    )

    assert len(rules) == 1
    assert rules[0]["sample_value"] == "Rubber outsole, reinforced toe cap."
    assert str(rules[0]["xpath"]).startswith("//div")

@pytest.mark.regression
def test_selector_self_heal_persists_valid_css_candidates_as_css_rules() -> None:
    rules = validated_xpath_rules(
        html="""
        <html>
          <body>
            <div class="custom-specs">Rubber outsole, reinforced toe cap.</div>
          </body>
        </html>
        """,
        candidates=[
            {
                "field_name": "specifications",
                "css_selector": ".custom-specs",
            }
        ],
        target_fields=["specifications"],
    )

    assert rules == [
        {
            "field_name": "specifications",
            "css_selector": ".custom-specs",
            "xpath": None,
            "regex": None,
            "sample_value": "Rubber outsole, reinforced toe cap.",
            "source": "selector_self_heal",
            "status": "validated",
            "is_active": True,
        }
    ]

@pytest.mark.regression
def test_extract_records_tracks_dom_observed_selector_traces_for_final_dom_fields() -> (
    None
):
    record = extract_records(
        """
        <html>
          <body>
            <main>
              <h1>DOM Observed Widget</h1>
              <span class="price">$19.99</span>
            </main>
          </body>
        </html>
        """,
        "https://example.com/products/dom-observed-widget",
        "ecommerce_detail",
        max_records=1,
    )[0]

    traces = record["_selector_traces"]
    assert traces["title"]["selector_kind"] == "css_selector"
    assert traces["title"]["selector_value"] == "h1"
    assert traces["title"]["selector_source"] == "dom_observed"
    assert traces["price"]["selector_kind"] == "css_selector"
    assert (
        traces["price"]["selector_value"]
        == "[itemprop='price'], .price, .product-price"
    )
    assert traces["price"]["selector_source"] == "dom_observed"
