from __future__ import annotations

from .test_detail_extractor_structured_sources import (
    MyntraAdapter,
    extract_records,
    json,
    pytest,
)

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_collection_url_with_visible_tile_prices() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Short Sleeve</h1>
        <div data-component-id="product-tile">
          <a href="/p/trail-shirt-123.html">Trail Shirt</a>
          <div data-component-id="display-price">
            <span aria-label="current price $27.00">$27.00</span>
          </div>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/c/mens-short-sleeve-shirts/",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_myntra_adapter_extracts_detail_media_and_variants() -> None:
    html = """
    <html>
      <head>
        <title>Myntra</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Myntra",
          "image": "https://constant.myntassets.com/web/assets/img/logo_2021.png"
        }
        </script>
        <script>
          window.__myx = {
            "pdpData": {
              "id": 30721580,
              "name": "KALINI Floral Embroidered Kurta",
              "brand": "KALINI",
              "baseColour": "pink and white",
              "mrp": 3196,
              "selectedSeller": {"discountedPrice": 735},
              "media": {
                "albums": [
                  {
                    "name": "default",
                    "images": [
                      {"secureSrc": "https://assets.myntassets.com/assets/images/30721580/image-1.jpg"},
                      {"secureSrc": "https://assets.myntassets.com/assets/images/30721580/image-2.jpg"},
                      {"secureSrc": "https://assets.myntassets.com/assets/images/30721580/image-3.jpg"}
                    ]
                  }
                ]
              },
              "colours": [
                {"label": "pink and white", "url": "/products/30721580"},
                {"label": "peach", "url": "/products/29861551"}
              ],
              "sizes": [
                {
                  "skuId": 98872105,
                  "label": "S",
                  "available": true,
                  "selectedSeller": {"discountedPrice": 735, "availableCount": 8}
                },
                {
                  "skuId": 98872106,
                  "label": "M",
                  "available": false,
                  "selectedSeller": {"discountedPrice": 735, "availableCount": 0}
                }
              ]
            }
          };
        </script>
      </head>
      <body>
        <h1>KALINI Floral Embroidered Kurta</h1>
      </body>
    </html>
    """

    adapter = MyntraAdapter()
    result = await adapter.extract(
        "https://www.myntra.com/kurtas/kalini/example/30721580/buy",
        html,
        "ecommerce_detail",
    )

    rows = extract_records(
        html,
        "https://www.myntra.com/kurtas/kalini/example/30721580/buy",
        "ecommerce_detail",
        max_records=5,
        adapter_records=result.records,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "KALINI Floral Embroidered Kurta"
    assert (
        record["image_url"]
        == "https://assets.myntassets.com/assets/images/30721580/image-1.jpg"
    )
    assert record["additional_images"] == [
        "https://assets.myntassets.com/assets/images/30721580/image-2.jpg",
        "https://assets.myntassets.com/assets/images/30721580/image-3.jpg",
    ]
    assert record["variant_count"] == 2

@pytest.mark.asyncio
@pytest.mark.regression
async def test_myntra_adapter_keeps_numeric_size_variants_from_related_urls() -> None:
    html = """
    <html>
      <head>
        <script>
          window.__myx = {
            "pdpData": {
              "id": 30191552,
              "name": "WROGN Men Woven Design Walking Shoes",
              "brand": "WROGN",
              "baseColour": "Black",
              "mrp": 3999,
              "selectedSeller": {"discountedPrice": 1399},
              "media": {"albums": []},
              "sizes": [
                {
                  "skuId": 97143404,
                  "label": "6",
                  "available": true,
                  "action": "/product/30191552/related/6?co=1"
                },
                {
                  "skuId": 97143405,
                  "label": "7",
                  "available": true,
                  "action": "/product/30191552/related/7?co=1"
                }
              ]
            }
          };
        </script>
      </head>
      <body>
        <h1>WROGN Men Woven Design Walking Shoes</h1>
      </body>
    </html>
    """
    page_url = (
        "https://www.myntra.com/sports-shoes/wrogn/"
        "wrogn-men-woven-design-walking-shoes/30191552/buy"
    )

    result = await MyntraAdapter().extract(page_url, html, "ecommerce_detail")
    rows = extract_records(
        html,
        page_url,
        "ecommerce_detail",
        max_records=5,
        adapter_records=result.records,
    )

    assert len(rows) == 1
    assert rows[0]["variant_count"] == 2
    assert [variant["size"] for variant in rows[0]["variants"]] == ["6", "7"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_myntra_adapter_allows_dom_description_fill_when_detail_payload_is_sparse() -> (
    None
):
    html = """
    <html>
      <head>
        <script>
          window.__myx = {
            "pdpData": {
              "id": 30721580,
              "name": "KALINI Floral Embroidered Kurta",
              "brand": "KALINI",
              "mrp": 3196,
              "selectedSeller": {"discountedPrice": 735},
              "media": {"albums": []},
              "sizes": []
            }
          };
        </script>
      </head>
      <body>
        <h1>KALINI Floral Embroidered Kurta</h1>
        <h2>Description</h2>
        <p>Soft cotton fabric with embroidered floral detailing.</p>
      </body>
    </html>
    """

    adapter = MyntraAdapter()
    result = await adapter.extract(
        "https://www.myntra.com/kurtas/kalini/example/30721580/buy",
        html,
        "ecommerce_detail",
    )

    rows = extract_records(
        html,
        "https://www.myntra.com/kurtas/kalini/example/30721580/buy",
        "ecommerce_detail",
        max_records=5,
        adapter_records=result.records,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "KALINI Floral Embroidered Kurta"
    assert (
        record["description"] == "Soft cotton fabric with embroidered floral detailing."
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_variant_axes_from_dom_controls_when_js_state_is_absent() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <label>
          Size
          <select name="size">
            <option value="">Choose size</option>
            <option value="s">S</option>
            <option value="m">M</option>
            <option value="l">L</option>
          </select>
        </label>
        <div class="color-swatch-group" aria-label="Color">
          <button type="button" aria-label="Black"></button>
          <button type="button" aria-label="Olive"></button>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 6
    assert isinstance(record["variants"], list)
    assert len(record["variants"]) == 6
    assert record["variants"][0]["size"] == "S"
    assert record["variants"][0]["color"] == "Black"

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_dicks_like_size_variants_from_button_grid() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Birkenstock Women's Arizona Big Buckle Soft Footbed Sandals</h1>
        <div class="image-viewer-swatch-col hmf-span-3">
          <button
            id="alt-image-viewer-wrapper-123"
            class="image-wrapper-padding image-wrapper-height image-viewer-swatch-wrapper"
            aria-label="View Image in Full Screen"
            type="button"
          ></button>
        </div>
        <section id="pdp-selector-attributes" class="selector-attributes-container">
          <pdp-attributes-components-label>
            <p><pdp-attributes-components-base-attribute-label><span>Shoe Size:</span></pdp-attributes-components-base-attribute-label></p>
          </pdp-attributes-components-label>
          <div class="hmf-grid selector-attribute-outer overflow-scroll">
            <hmf-selectable>
              <div class="hmf-selectable-container hmf-display-flex hmf-body-m hmf-flex-wrap">
                <div class="hmf-option-container">
                  <button class="hmf-selectable-base hmf-selectable-unselected" aria-label="5.0/5.5 US (36 EU)" type="button">
                    <span>5.0/5.5 US (36 EU)</span>
                  </button>
                </div>
                <div class="hmf-option-container">
                  <button class="hmf-selectable-base hmf-selectable-unselected" aria-label="6.0/6.5 US (37 EU)" type="button">
                    <span>6.0/6.5 US (37 EU)</span>
                  </button>
                </div>
                <div class="hmf-option-container">
                  <button class="hmf-selectable-base hmf-selectable-unselected" aria-label="7.0/7.5 US (38 EU)" type="button">
                    <span>7.0/7.5 US (38 EU)</span>
                  </button>
                </div>
              </div>
            </hmf-selectable>
          </div>
        </section>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.dickssportinggoods.com/p/example/product",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["variants", "size"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 3
    assert [row["size"] for row in record["variants"]] == [
        "5.0/5.5 US (36 EU)",
        "6.0/6.5 US (37 EU)",
        "7.0/7.5 US (38 EU)",
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_requires_cartesian_color_size_dom_variants() -> None:
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Suede Runner</h1>
          <form class="product-form" action="/cart/add">
            <fieldset class="size-selector">
              <legend>Size</legend>
              <button type="button">8</button>
              <button type="button">9</button>
              <button type="button">10</button>
            </fieldset>
            <div class="color-swatch-group" aria-label="Color">
              <button type="button" aria-label="Black"></button>
              <button type="button" aria-label="Red"></button>
            </div>
          </form>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/suede-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 6
    assert all(row.get("size") and row.get("color") for row in record["variants"])

@pytest.mark.regression
def test_extract_ecommerce_detail_expands_rich_color_variants_with_dom_sizes() -> None:
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "title": "Arizona Birko-Flor",
                "price": 117.95,
                "currencyCode": "USD",
                "variants": [
                  {
                    "id": "white",
                    "sku": "552681",
                    "color": "White",
                    "price": 117.95,
                    "image": "https://example.com/552681.jpg"
                  },
                  {
                    "id": "black",
                    "sku": "51791",
                    "color": "Black",
                    "price": 117.95,
                    "image": "https://example.com/51791.jpg"
                  },
                  {
                    "id": "dark-brown",
                    "sku": "51703",
                    "color": "Dark Brown",
                    "price": 117.95,
                    "image": "https://example.com/51703.jpg"
                  }
                ]
              }
            }
          }
        }
        </script>
      </head>
      <body>
        <main class="product-detail">
          <h1>Arizona Birko-Flor</h1>
          <form class="product-form" action="/cart/add">
            <fieldset class="size-selector">
              <legend>Size</legend>
              <button type="button">36</button>
              <button type="button">37</button>
            </fieldset>
          </form>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.birkenstock.com/us/arizona-birko-flor/arizona-core-birkoflor-0-eva-u_1.html",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "size", "color", "price", "currency"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 6
    assert {row["color"] for row in record["variants"]} == {
        "White",
        "Black",
        "Dark Brown",
    }
    assert {row["size"] for row in record["variants"]} == {"36", "37"}
    assert all(row.get("image_url") for row in record["variants"])

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_labeled_image_color_swatches() -> None:
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Boho Bangle Bracelets, Set of 3</h1>
          <form class="sku-selection">
            <fieldset data-qa-color>
              <legend>Color: <span>Cream/Silver</span></legend>
              <input id="color-012" name="selectedColor" value="012" type="radio" checked>
              <label for="color-012">
                <img src="https://images.example/108064080_012_s.jpg" alt="Cream/Silver">
              </label>
              <input id="color-001" name="selectedColor" value="001" type="radio">
              <label for="color-001">
                <img src="https://images.example/108064080_001_s.jpg" alt="Black/Silver">
              </label>
              <input id="color-020" name="selectedColor" value="020" type="radio">
              <label for="color-020">
                <img src="https://images.example/108064080_020_s.jpg" alt="Brown / Gold">
              </label>
            </fieldset>
            <fieldset data-qa-size>
              <legend>Size</legend>
              <input id="size-one" name="selectedSize" value="0000" type="radio" checked>
              <label for="size-one">One Size</label>
            </fieldset>
          </form>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.anthropologie.com/shop/boho-bangle-bracelets-set-of-3",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "color"],
    )

    record = rows[0]
    assert record["variant_count"] == 3
    assert [row["color"] for row in record["variants"]] == [
        "Cream/Silver",
        "Black/Silver",
        "Brown / Gold",
    ]
    assert all(row.get("image_url") for row in record["variants"])

@pytest.mark.regression
def test_extract_ecommerce_detail_guarded_dom_cartesian_keeps_axis_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.extract.detail.variants import (
        dom_extraction as detail_dom_variant_extraction,
    )

    monkeypatch.setattr(
        detail_dom_variant_extraction,
        "DOM_VARIANT_CARTESIAN_COMBO_LIMIT",
        4,
    )
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Suede Runner</h1>
          <form class="product-form" action="/cart/add">
            <fieldset class="size-selector">
              <legend>Size</legend>
              <button type="button">8</button>
              <button type="button">9</button>
              <button type="button">10</button>
            </fieldset>
            <div class="color-swatch-group" aria-label="Color">
              <button type="button" aria-label="Black"></button>
              <button type="button" aria-label="Red"></button>
              <button type="button" aria-label="White"></button>
            </div>
          </form>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/suede-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 6
    size_rows = [row for row in record["variants"] if row.get("size")]
    color_rows = [row for row in record["variants"] if row.get("color")]
    assert {row.get("size") for row in size_rows} == {"8", "9", "10"}
    assert {row.get("color") for row in color_rows} == {"Black", "Red", "White"}
    assert all(not row.get("color") for row in size_rows)
    assert all(not row.get("size") for row in color_rows)

@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_related_product_carousel_variants() -> None:
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Going Coconuts</h1>
          <p>Neutral coconut shades only.</p>
        </main>
        <section class="related-products carousel">
          <div class="color-swatch-group" aria-label="Color">
            <button type="button" aria-label="Blowin Smoke"></button>
            <button type="button" aria-label="Forever Yours"></button>
          </div>
        </section>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://colourpop.com/products/going-coconuts-eyeshadow-palette",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert "variants" not in rows[0]

@pytest.mark.regression
def test_extract_ecommerce_detail_prunes_js_state_related_product_variants() -> None:
    related_variants = [
        {
            "id": "pink-dreams",
            "title": "Pink Dreams",
            "color": "Pink Dreams",
            "url": "https://colourpop.com/products/pink-dreams-shadow-palette",
            "available": True,
        },
        {
            "id": "silver-lining",
            "title": "Silver Lining",
            "color": "Silver Lining",
            "url": "https://colourpop.com/products/silver-lining-shadow-palette",
            "available": True,
        },
    ]
    html = f"""
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {{
          "props": {{
            "pageProps": {{
              "product": {{
                "id": "going-coconuts",
                "title": "Going Coconuts",
                "url": "https://colourpop.com/products/going-coconuts-eyeshadow-palette",
                "size": 24,
                "price": 14,
                "currency": "USD",
                "variants": {json.dumps(related_variants)}
              }}
            }}
          }}
        }}
        </script>
        <script type="application/json">
        {{"arrows": {{"size": {{"value": 24, "unit": "px"}}, "enabled": true}}}}
        </script>
      </head>
      <body><main><h1>Going Coconuts</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://colourpop.com/products/going-coconuts-eyeshadow-palette",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "variants" not in record
    assert "variant_count" not in record
    assert "size" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_structured_variants_with_axes() -> None:
    variants = []
    for color in ("Black", "Ivory", "Red"):
        for size in ("6", "8", "10", "12"):
            variants.append(
                {
                    "id": f"{color.lower()}-{size}",
                    "sku": f"KM-{color[:1].upper()}{size}",
                    "selectedOptions": [
                        {"name": "Color", "value": color},
                        {"name": "Size", "value": size},
                    ],
                }
            )
    html = f"""
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {{
          "props": {{
            "pageProps": {{
              "product": {{
                "id": "dress-1",
                "title": "Tailored Midi Dress",
                "currency": "GBP",
                "variants": {json.dumps(variants)}
              }}
            }}
          }}
        }}
        </script>
      </head>
      <body><main><h1>Tailored Midi Dress</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/tailored-midi-dress",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 12
    assert all(row.get("color") and row.get("size") for row in record["variants"])
