from __future__ import annotations

from .test_detail_extractor_structured_sources import (
    build_detail_record,
    extract_detail_records,
    extract_records,
    pytest,
)


@pytest.mark.regression
def test_build_detail_record_keeps_product_image_when_identity_code_is_in_url() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Old Skool Shoe</h1></main></body></html>",
        "https://www.vans.com/en-us/p/old-skool-VN000E9TBPG",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Old Skool Shoe",
                "image_url": "https://assets.vans.com/images/t_Thumbnail/v1/VN000E9TBPG-HERO/Old-Skool-Shoe-VANS-HERO.png",
            }
        ],
    )

    assert "VN000E9TBPG-HERO" in record["image_url"]


@pytest.mark.regression
def test_build_detail_record_rejects_cross_sell_images_by_filename_identity() -> None:
    html = "<html><body><main><h1>Nike Dunk Low Retro White Black Panda</h1></main></body></html>"

    record = build_detail_record(
        html,
        "https://stockx.com/nike-dunk-low-retro-white-black-2021",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Nike Dunk Low Retro White Black Panda",
                "image_url": "https://images.stockx.com/images/Nike-Dunk-Low-Retro-White-Black-2021-Product.jpg",
                "additional_images": [
                    "https://images.stockx.com/360/Nike-Dunk-Low-Retro-White-Black-2021/Images/Nike-Dunk-Low-Retro-White-Black-2021/Lv2/img01.jpg",
                    "https://images.stockx.com/images/Nike-Dunk-Low-Grey-Fog-Product.jpg",
                    "https://images.stockx.com/images/Nike-Dunk-Low-Court-Purple-Product.jpg",
                ],
            }
        ],
    )

    assert record["image_url"].endswith(
        "Nike-Dunk-Low-Retro-White-Black-2021-Product.jpg"
    )
    assert record["additional_images"] == [
        "https://images.stockx.com/360/Nike-Dunk-Low-Retro-White-Black-2021/Images/Nike-Dunk-Low-Retro-White-Black-2021/Lv2/img01.jpg"
    ]


@pytest.mark.regression
def test_build_detail_record_rejects_same_cdn_different_product_image() -> None:
    record = build_detail_record(
        "<html><body><main><h1>RUSTIC COTTON T-SHIRT</h1></main></body></html>",
        "https://www.zara.com/us/en/rustic-cotton-t-shirt-p04424306.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "RUSTIC COTTON T-SHIRT",
                "image_url": "https://static.zara.net/assets/public/5326/04424306104-p/04424306104-p.jpg",
                "additional_images": [
                    "https://static.zara.net/assets/public/c95f/04424306104-a1/04424306104-a1.jpg",
                    "https://static.zara.net/assets/public/db43/07223038250-f1/07223038250-f1.jpg",
                ],
            }
        ],
    )

    assert record["additional_images"] == [
        "https://static.zara.net/assets/public/c95f/04424306104-a1/04424306104-a1.jpg"
    ]


@pytest.mark.regression
def test_build_detail_record_formats_currency_prices_and_drops_bad_discounts() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Jogger</h1></main></body></html>",
        "https://shop.lululemon.com/p/men-joggers/Abc-Jogger/_/prod8530240",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Jogger",
                "price": "128.000000",
                "original_price": "128.000000",
                "currency": "USD",
                "discount_amount": "223",
                "discount_percentage": "225",
            }
        ],
    )

    assert record["price"] == "128.00"
    assert record["original_price"] == "128.00"
    assert "discount_amount" not in record
    assert "discount_percentage" not in record


@pytest.mark.regression
def test_build_detail_record_drops_sale_price_when_not_below_current_price() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Rambler Ceramic Stackable 8Oz</h1></main></body></html>",
        "https://www.yeti.com/drinkware/tumblers/rambler-ceramic-stackable-8oz.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Rambler Ceramic Stackable 8Oz",
                "price": "25.00",
                "sale_price": "28",
                "original_price": "28.00",
                "currency": "USD",
            }
        ],
    )

    assert record["price"] == "25.00"
    assert record["original_price"] == "28.00"
    assert "sale_price" not in record


@pytest.mark.regression
def test_build_detail_record_drops_polluted_parent_size_option_list() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Rambler Ceramic Stackable 8Oz</h1></main></body></html>",
        "https://www.yeti.com/drinkware/tumblers/rambler-ceramic-stackable-8oz.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Rambler Ceramic Stackable 8Oz",
                "price": "25.00",
                "currency": "USD",
                "size": "8 oz Ceramic 8 oz Ceramic 16 oz 20 oz 30 oz Compare Size",
            }
        ],
    )

    assert "size" not in record


@pytest.mark.regression
def test_build_detail_record_drops_numeric_parent_color_when_variants_have_labels() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Tommy Hilfiger Mens Hiday Casualized Hybrid Oxfords</h1></main></body></html>",
        "https://www.macys.com/shop/product/tommy-hilfiger-mens-hiser-casualized-hybrid-oxfords?ID=19526232",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Tommy Hilfiger Mens Hiday Casualized Hybrid Oxfords",
                "price": "54.50",
                "currency": "USD",
                "sku": "19526232",
                "color": "9501719",
                "variants": [{"size": "7M", "color": "Dark Brown"}],
            }
        ],
    )

    assert "color" not in record
    assert record["variants"][0]["size"] == "7M"
    assert record["variants"][0]["color"] == "Dark Brown"


@pytest.mark.regression
def test_extract_detail_rejects_same_url_model_number_title_mismatch() -> None:
    rows = extract_detail_records(
        "<html><body><main><h1>iPhone 16 Plus Unlocked</h1></main></body></html>",
        "https://www.backmarket.com/en-us/p/iphone-15-plus",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "iPhone 16 Plus Unlocked",
                "price": "537",
                "currency": "USD",
                "sku": "IPHONE-15-PLUS",
            }
        ],
    )

    assert rows == []


@pytest.mark.regression
def test_extract_detail_accepts_same_url_model_code_when_record_identity_matches() -> (
    None
):
    requested_url = (
        "https://www.kitchenaid.com/countertop-appliances/food-processors/"
        "processors/p.13-cup-food-processor.KFP1318CU.html"
    )

    rows = extract_detail_records(
        "<html><body><main><h1>13-Cup Food Processor</h1></main></body></html>",
        requested_url,
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "13-Cup Food Processor",
                "url": requested_url,
                "price": "229.99",
                "currency": "USD",
                "sku": "KFP1318CU",
                "brand": "KitchenAid",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["sku"] == "KFP1318CU"


@pytest.mark.regression
def test_extract_detail_accepts_same_url_bare_size_number_difference() -> None:
    rows = extract_detail_records(
        "<html><body><main><h1>Cloud Runner Size 12</h1></main></body></html>",
        "https://example.com/products/cloud-runner-size-10",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Cloud Runner Size 12",
                "price": "84.00",
                "currency": "USD",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Cloud Runner Size 12"


@pytest.mark.regression
def test_extract_detail_accepts_same_url_generic_numeric_path_difference() -> None:
    rows = extract_detail_records(
        "<html><body><main><h1>Product 2 Pack</h1></main></body></html>",
        "https://example.com/product/1234",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Product 2 Pack",
                "price": "12.00",
                "currency": "USD",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Product 2 Pack"


@pytest.mark.regression
def test_build_detail_record_replaces_low_signal_prime_title_from_identity() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Stan Smith Shoes</h1></main></body></html>",
        "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "prime",
                "price": "100",
                "currency": "USD",
                "sku": "M20324",
            }
        ],
    )

    assert record["title"] != "prime"
    assert "Stan Smith Shoes" in record["title"]


@pytest.mark.regression
def test_missing_detail_title_does_not_fall_back_to_parent_category_segment() -> None:
    record = build_detail_record(
        "<html><body><main><div data-testid='price'>$12.00</div></main></body></html>",
        "https://example.com/mens-shoes/product/1234.html",
        "ecommerce_detail",
        None,
    )

    assert "title" not in record


@pytest.mark.regression
def test_build_detail_record_drops_redundant_product_details() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Italian Seersucker Sutton Suit</h1></main></body></html>",
        "https://www.toddsnyder.com/collections/slim-fit-suits-tuxedos/products/italian-seersucker-sutton-suit-2",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Italian Seersucker Sutton Suit",
                "price": "996",
                "currency": "USD",
                "description": "A lightweight Italian seersucker suit.",
                "product_details": "A lightweight Italian seersucker suit.",
            }
        ],
    )

    assert record["description"] == "A lightweight Italian seersucker suit."
    assert "product_details" not in record


@pytest.mark.regression
def test_build_detail_record_backfills_low_signal_one_dollar_prices_from_dom() -> None:
    html = """
    <html><body><main>
      <h1>Stan Smith Shoes</h1>
      <div data-testid="price">$100.00</div>
    </main></body></html>
    """

    record = build_detail_record(
        html,
        "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Stan Smith Shoes",
                "price": "1",
                "currency": "USD",
                "variants": [
                    {
                        "variant_id": "M20324-9",
                        "sku": "M20324-9",
                        "price": "1",
                        "currency": "USD",
                        "option_values": {"size": "9"},
                    }
                ],
                "selected_variant": {
                    "variant_id": "M20324-9",
                    "sku": "M20324-9",
                    "price": "1",
                    "currency": "USD",
                    "option_values": {"size": "9"},
                },
            }
        ],
    )

    assert record["price"] == "100.00"
    assert record["variants"][0]["price"] == "100.00"


@pytest.mark.regression
def test_extract_detail_corrects_100x_structured_price_from_visible_dom_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Kitchen Mixer",
          "offers": {"price": "22999.00", "priceCurrency": "USD"}
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Kitchen Mixer</h1>
          <div data-testid="price">$229.99</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/kitchen-mixer",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "229.99"


@pytest.mark.regression
def test_build_detail_record_corrects_parent_price_from_variant_magnitude_match() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Road Running Shoes</h1></main></body></html>",
        "https://example.com/products/road-running-shoes",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Road Running Shoes",
                "price": "9999.00",
                "currency": "USD",
                "variants": [
                    {
                        "variant_id": "ROAD-9",
                        "price": "99.99",
                        "currency": "USD",
                        "option_values": {"size": "9"},
                    }
                ],
            }
        ],
    )

    assert record["price"] == "99.99"
    assert record["variants"][0]["price"] == "99.99"


@pytest.mark.regression
def test_extract_detail_skips_installment_price_when_total_price_exists() -> None:
    html = """
    <html><body><main>
      <h1>Sectional Sofa</h1>
      <div class="price financing">Pay in 4 payments of $50.00 with Klarna</div>
      <div class="price total">$200.00</div>
    </main></body></html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/sectional-sofa",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "200.00"


@pytest.mark.regression
def test_build_detail_record_replaces_uuid_sku_with_merch_code() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Nike Dunk Low Retro White Black Panda</h1></main></body></html>",
        "https://stockx.com/nike-dunk-low-retro-white-black-2021",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "sku": "5e6a1e57-1c7d-435a-82bd-5666a13560fe",
                "title": "Nike Dunk Low Retro White Black Panda",
                "product_details": "Style DD1391-100 Colorway White/Black Retail Price $115",
            }
        ],
    )

    assert record["sku"] == "DD1391-100"
    assert record["part_number"] == "DD1391-100"


@pytest.mark.regression
def test_build_detail_record_drops_stockx_market_cta_variant_labels() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Nike Dunk Low Retro White Black Panda</h1></main></body></html>",
        "https://stockx.com/nike-dunk-low-retro-white-black-2021",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Nike Dunk Low Retro White Black Panda",
                "variants": [
                    {
                        "url": "https://stockx.com/buy/nike-dunk-low-retro-white-black-2021?defaultBid=true",
                        "color": "See All",
                    },
                    {
                        "url": "https://stockx.com/buy/nike-dunk-low-retro-white-black-2021?defaultBid=true",
                        "color": "View Market Data",
                    },
                    {
                        "url": "https://stockx.com/buy/nike-dunk-low-retro-white-black-2021?defaultBid=true",
                        "color": "Sell Now for",
                    },
                ],
            }
        ],
    )

    assert "variants" not in record
    assert "variant_count" not in record


@pytest.mark.regression
def test_build_detail_record_strips_numeric_size_tail_from_stockx_description() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Nike Dunk Low Retro White Black Panda</h1></main></body></html>",
        "https://stockx.com/nike-dunk-low-retro-white-black-2021",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Nike Dunk Low Retro White Black Panda",
                "description": (
                    "Nike put its timeless color-blocking to work with the Nike Dunk "
                    "Low Retro White Black. The Nike Dunk Low Retro White Black "
                    "released in January of 2021 and retailed for $100. To shop "
                    "all Nike Dunks, click here. 5 6 6.5 7 7.5 8 8.5 9 9.5 "
                    "10 10.5 11 11.5 12 12.5 13 14 15"
                ),
            }
        ],
    )

    assert record["description"].endswith("To shop all Nike Dunks, click here.")
    assert " 5 6 6.5" not in record["description"]


@pytest.mark.regression
def test_build_detail_record_drops_costco_shell_long_text_labels() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Sleep Number Ultimate 12&quot; Mattress</h1></main></body></html>",
        "https://www.costco.com/p/-/sleep-number-ultimate-12-mattress/4201005351?langId=-1",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": 'Sleep Number Ultimate 12" Mattress',
                "description": "Product Label",
                "specifications": "Specifications",
                "product_details": (
                    "Product Label Powered by Product details have been supplied by the manufacturer "
                    "and are hosted by a third party. View More"
                ),
            }
        ],
    )

    assert "description" not in record
    assert "specifications" not in record
    assert "product_details" not in record


@pytest.mark.regression
def test_raw_json_detail_postprocess_drops_costco_shell_long_text_labels() -> None:
    rows = extract_records(
        """
        {
          "title": "Sleep Number Ultimate 12\\" Mattress",
          "description": "Product Label",
          "specifications": "Specifications",
          "product_details": "Product Label Powered by Product details have been supplied by the manufacturer View More",
          "price": "2299.99"
        }
        """,
        "https://www.costco.com/p/-/sleep-number-ultimate-12-mattress/4201005351?langId=-1",
        "ecommerce_detail",
        max_records=5,
        content_type="application/json",
    )

    assert rows[0]["title"] == 'Sleep Number Ultimate 12" Mattress'
    assert "description" not in rows[0]
    assert "specifications" not in rows[0]
    assert "product_details" not in rows[0]


@pytest.mark.regression
def test_extract_detail_infers_costco_textual_variant_sizes_from_titles() -> None:
    detail = build_detail_record(
        "<html><body><main><h1>Sleep Number Ultimate 12&quot; Mattress</h1></main></body></html>",
        "https://www.costco.com/p/-/sleep-number-ultimate-12-mattress/4201005351?langId=-1",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": 'Sleep Number Ultimate 12" Mattress',
                "variants": [
                    {
                        "sku": "1981348",
                        "title": 'Sleep Number Ultimate 12" Mattress Only, Queen',
                        "price": "2299.99",
                        "currency": "USD",
                        "availability": "in_stock",
                    },
                    {
                        "sku": "1981349",
                        "title": 'Sleep Number Ultimate 12" Mattress Only, King',
                        "price": "2299.99",
                        "currency": "USD",
                        "availability": "in_stock",
                    },
                ],
                "selected_variant": {
                    "sku": "1981348",
                    "title": 'Sleep Number Ultimate 12" Mattress Only, Queen',
                    "price": "2299.99",
                    "currency": "USD",
                    "availability": "in_stock",
                },
            }
        ],
    )

    assert detail is not None
    assert detail["title"] == 'Sleep Number Ultimate 12" Mattress'
    assert '12"' in detail["title"]
    assert len(detail["variants"]) == 2
    assert detail["variants"][0]["sku"] == "1981348"
    assert {variant["size"] for variant in detail["variants"]} == {"Queen", "King"}


@pytest.mark.regression
def test_build_detail_record_strips_review_copy_from_color_scalar() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Blouson Twill Utility Jacket</h1></main></body></html>",
        "https://www.nordstrom.com/s/treasure-and-bond-blouson-twill-utility-jacket/8045019",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Blouson Twill Utility Jacket",
                "color": "Ivory Dove Customers say the fit runs true to size",
            }
        ],
    )

    assert record["color"] == "Ivory Dove"


@pytest.mark.regression
def test_build_detail_record_drops_polluted_parent_color_dump_when_variants_are_cleaner() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Rambler 8 oz Stackable Cup</h1></main></body></html>",
        "https://www.yeti.com/drinkware/tumblers/21071507376.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Rambler 8 oz Stackable Cup",
                "color": (
                    "Desert Bloom Trio 1 2 3 4 5 6 7 8 9 10 - + "
                    "Rescue Red/White/Navy Big Sky Blue"
                ),
                "variants": [
                    {"color": "Desert Bloom Trio"},
                    {"color": "Rescue Red/White/Navy"},
                    {"color": "Big Sky Blue"},
                ],
            }
        ],
    )

    assert "color" not in record
    assert {variant.get("color") for variant in record["variants"]} == {
        "Desert Bloom Trio",
        "Rescue Red/White/Navy",
        "Big Sky Blue",
    }


@pytest.mark.regression
def test_build_detail_record_prefers_dom_sizes_over_existing_color_only_variants() -> (
    None
):
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Speedcat Sneakers</h1>
          <form class="product-form" action="/cart/add">
            <label>
              Size
              <select name="size">
                <option value="">Choose size</option>
                <option value="uk-7">UK 7</option>
                <option value="uk-8">UK 8</option>
                <option value="uk-9">UK 9</option>
              </select>
            </label>
          </form>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://in.puma.com/in/en/pd/speedcat-sneakers/406329?swatch=02",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Speedcat Sneakers",
                "color": "For All Time Red-PUMA White",
                "variants": [
                    {"color": "PUMA Black-PUMA White"},
                    {"color": "For All Time Red-PUMA White"},
                    {"color": "Strawberry Burst-PUMA Black"},
                ],
            }
        ],
    )

    assert record["variants"] == [
        {"size": "UK 7"},
        {"size": "UK 8"},
        {"size": "UK 9"},
    ]
    assert record["color"] == "For All Time Red-PUMA White"


@pytest.mark.regression
def test_build_detail_record_drops_document_link_only_description() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Lansdale Sand Black Transitional Opal Glass Lantern Pendant Light</h1></main></body></html>",
        "https://www.lowes.com/pd/Minka-Lavery-Lansdale-Sand-Black-Transitional-Opal-Glass-Lantern-Pendant-Light/1001420790",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Lansdale Sand Black Transitional Opal Glass Lantern Pendant Light",
                "description": "Warranty Guide Prop65 Warning Label Use and Care Manual Installation Manual Dimensions Guide",
            }
        ],
    )

    assert "description" not in record
