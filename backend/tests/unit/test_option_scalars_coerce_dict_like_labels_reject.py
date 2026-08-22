from __future__ import annotations

from .test_field_value_core import clean_text, coerce_field_value, extract_urls, infer_brand_from_product_url, infer_brand_from_title_marker, is_title_noise, merge_variant_rows, public_record_data_for_surface, pytest  # fmt: skip


@pytest.mark.unit
def test_option_scalars_coerce_dict_like_labels_and_reject_null_tokens() -> None:
    assert (
        coerce_field_value(
            "color",
            "{'id': 'black-onyx', 'title': 'black onyx'}",
            "https://example.com/p/socks",
        )
        == "black onyx"
    )
    assert coerce_field_value("color", "None", "https://example.com/p/wash") is None
    assert coerce_field_value("size", "- / null", "https://example.com/p/bag") is None
    assert (
        coerce_field_value(
            "size",
            "Please select US EU",
            "https://example.com/p/sandal",
        )
        is None
    )


@pytest.mark.unit
def test_title_coerces_nested_dict_like_label_instead_of_stringifying_object() -> None:
    assert (
        coerce_field_value(
            "title",
            (
                # coerce_field_value ignores the top-level UI/display label ("Name")
                # and prefers values.label when this dict-like shape carries the title.
                "{'id': 20005, 'key': 'name', 'label': 'Name', 'type': '', "
                "'multiSelect': False, 'values': {'id': 20005, "
                "'label': 'Emperor 100% Arctic Duck Down Duvet (8.5 Tog)', "
                "'value': 'name'}}"
            ),
            "https://www.harrods.com/en-gb/p/brinkhaus-emperor-duvet",
        )
        == "Emperor 100% Arctic Duck Down Duvet (8.5 Tog)"
    )


@pytest.mark.unit
def test_color_scalar_extracts_value_from_prefixed_product_copy() -> None:
    assert (
        coerce_field_value(
            "color",
            "for Sony WH-1000XM5 Wireless Noise-canceling Headphones - Black: Black",
            "https://example.com/p/headphones",
        )
        == "Black"
    )
    assert (
        coerce_field_value(
            "color",
            "Black/Red Style: HJ0139-045",
            "https://example.com/p/shirt",
        )
        == "Black/Red"
    )


@pytest.mark.unit
def test_clean_text_strips_leading_css_in_js_noise() -> None:
    assert (
        clean_text(".css-7u5e79{margin:0.5rem 0rem;} The Legend of Zelda")
        == "The Legend of Zelda"
    )


@pytest.mark.unit
def test_is_title_noise_keeps_short_non_numeric_product_titles() -> None:
    assert is_title_noise("Hat") is False
    assert is_title_noise("UGG") is False
    assert is_title_noise("Tie") is False


@pytest.mark.unit
def test_extract_urls_trims_trailing_punctuation_from_embedded_urls() -> None:
    urls = extract_urls(
        "Docs: https://example.com/alpha), https://example.com/beta.",
        "https://base.example",
    )

    assert urls == [
        "https://example.com/alpha",
        "https://example.com/beta",
    ]


@pytest.mark.unit
def test_extract_urls_rejects_concatenated_absolute_urls() -> None:
    # Concatenated URLs are corrupted data (two products merged into one string),
    # not two valid products. Reject entirely.
    urls = extract_urls(
        "https://www.asos.com/us/foo/prd/1https://www.asos.com/us/bar/prd/2",
        "https://www.asos.com/us/foo/prd/1",
    )

    assert urls == []


@pytest.mark.unit
def test_extract_urls_preserves_balanced_parentheses_and_brackets() -> None:
    urls = extract_urls(
        "Docs: https://example.com/release_(2026), https://example.com/archive/[spring].",
        "https://base.example",
    )

    assert urls == [
        "https://example.com/release_(2026)",
        "https://example.com/archive/[spring]",
    ]


@pytest.mark.unit
def test_extract_urls_rejects_malformed_relative_image_fragments() -> None:
    assert (
        extract_urls(
            "g_auto/69721f2e7c934d909168a80e00818569_9366/Stan_Smith_Shoes_White_M20324_01_standard.jpg",
            "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        )
        == []
    )
    assert (
        extract_urls(
            "R0lGODlhAQABAIAAAP/wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==",
            "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        )
        == []
    )


@pytest.mark.unit
def test_infer_brand_from_title_marker_keeps_leading_trademark_brand_token() -> None:
    assert infer_brand_from_title_marker("®Nike Court Vision Low") == "®Nike"


@pytest.mark.unit
def test_infer_brand_from_product_url_skips_overlong_slug_and_keeps_valid_match() -> (
    None
):
    assert (
        infer_brand_from_product_url(
            url=(
                "https://example.com/acme-widget-prime/"
                "one-two-three-four-five-six-seven-eight-nine-widget-prime"
            ),
            title="Widget Prime",
        )
        == "Acme"
    )


@pytest.mark.unit
def test_infer_brand_from_product_url_rejects_numeric_product_id_prefix() -> None:
    assert (
        infer_brand_from_product_url(
            url="https://example.com/products/492216804-black-leather-belts-for-men",
            title="Black Leather Belts for Men",
        )
        is None
    )


@pytest.mark.unit
def test_coerce_color_rejects_single_digit_from_quantity_input() -> None:
    assert coerce_field_value("color", "1", "https://example.com/p") is None
    assert coerce_field_value("color", "2", "https://example.com/p") is None
    assert coerce_field_value("color", "99", "https://example.com/p") is None


@pytest.mark.unit
def test_coerce_color_keeps_valid_color_names() -> None:
    assert (
        coerce_field_value("color", "Black Onyx", "https://example.com/p")
        == "Black Onyx"
    )
    assert (
        coerce_field_value("color", "Navy Blue", "https://example.com/p") == "Navy Blue"
    )


@pytest.mark.unit
def test_coerce_color_strips_color_details_suffix() -> None:
    assert (
        coerce_field_value("color", "Huxley Color Details", "https://example.com/p")
        == "Huxley"
    )


@pytest.mark.unit
def test_coerce_color_strips_trailing_style_codes() -> None:
    assert (
        coerce_field_value("color", "Mf White Hq7978 103", "https://example.com/p")
        == "White"
    )
    assert (
        coerce_field_value("color", "White Hq7978 103", "https://example.com/p")
        == "White"
    )


@pytest.mark.unit
def test_coerce_color_strips_code_tail_without_dropping_prefix() -> None:
    assert (
        coerce_field_value("color", "Nike Mf White Hq7978 103", "https://example.com/p")
        == "Nike White"
    )


@pytest.mark.unit
def test_coerce_color_rejects_tracking_pixel_classes() -> None:
    assert coerce_field_value("color", "_clck", "https://example.com/p") is None
    assert coerce_field_value("color", "_fbp", "https://example.com/p") is None


@pytest.mark.unit
def test_coerce_color_rejects_internal_swatch_codes() -> None:
    """JSON-LD ``"color":["SMDB","FGE","OLGG",...]`` exposes internal swatch
    codes (Patagonia pattern). Real human-readable colors render in mixed
    case ("Bobcat Brown", "Aquatic Blue"). All-caps short tokens are almost
    always internal codes and must be rejected so a real value can win.
    """
    # Vowel-less consonant clusters and other short all-caps codes are codes.
    assert coerce_field_value("color", "SMDB", "https://example.com/p") is None
    assert coerce_field_value("color", "OLGG", "https://example.com/p") is None
    assert coerce_field_value("color", "BLK", "https://example.com/p") is None
    assert coerce_field_value("color", "AQT", "https://example.com/p") is None
    # Mixed-case short colors and longer human-readable values are kept.
    assert coerce_field_value("color", "Tan", "https://example.com/p") == "Tan"
    assert coerce_field_value("color", "mint", "https://example.com/p") == "mint"
    assert coerce_field_value("color", "cream", "https://example.com/p") == "cream"
    assert (
        coerce_field_value("color", "Bobcat Brown", "https://example.com/p")
        == "Bobcat Brown"
    )
    assert (
        coerce_field_value("color", "Aquatic Blue", "https://example.com/p")
        == "Aquatic Blue"
    )


@pytest.mark.unit
def test_coerce_color_list_skips_opaque_codes_for_real_value() -> None:
    """When JSON-LD payload exposes a list of color codes mixed with real
    names, the first real name should win.
    """
    assert (
        coerce_field_value(
            "color",
            ["SMDB", "Bobcat Brown", "OLGG"],
            "https://example.com/p",
        )
        == "Bobcat Brown"
    )
    # All codes -> drop entirely so a downstream tier can fill the gap.
    assert (
        coerce_field_value(
            "color",
            ["SMDB", "OLGG", "BLK"],
            "https://example.com/p",
        )
        is None
    )


@pytest.mark.parametrize(
    "label",
    ["Photos", "Verified Purchases", "Reviews", "Description", "Specifications"],
)
@pytest.mark.unit
def test_coerce_size_rejects_ui_tab_labels(label: str) -> None:
    assert coerce_field_value("size", label, "https://example.com/p") is None


@pytest.mark.unit
def test_coerce_size_keeps_valid_sizes() -> None:
    assert coerce_field_value("size", "M", "https://example.com/p") == "M"
    assert coerce_field_value("size", "10", "https://example.com/p") == "10"
    assert coerce_field_value("size", "XL", "https://example.com/p") == "XL"


@pytest.mark.unit
def test_extract_urls_filters_placeholder_images() -> None:
    assert (
        extract_urls("https://via.placeholder.com/600", "https://example.com/p") == []
    )
    assert (
        extract_urls("https://cdn.example.com/pixel.gif", "https://example.com/p") == []
    )


@pytest.mark.unit
def test_extract_urls_filters_concatenated_urls() -> None:
    assert (
        extract_urls(
            "https://www.selfridges.com/p/123/https:/www.mytheresa.com/p/456",
            "https://example.com/p",
        )
        == []
    )


@pytest.mark.unit
def test_extract_urls_keeps_normal_urls() -> None:
    urls = extract_urls(
        "https://cdn.example.com/product/image.jpg", "https://example.com/p"
    )
    assert len(urls) == 1
    assert "product/image.jpg" in urls[0]


@pytest.mark.unit
def test_public_firewall_rejects_concatenated_url() -> None:
    record = {
        "url": "https://www.selfridges.com/p/123/https:/www.mytheresa.com/p/456",
        "title": "Test Product",
    }
    data, rejected = public_record_data_for_surface(
        record, surface="ecommerce_detail", page_url="https://www.selfridges.com/p/123"
    )
    assert "url" not in data
    assert rejected.get("url") == "empty_after_coercion"


@pytest.mark.unit
def test_integer_fields_reject_embedded_numeric_junk() -> None:
    assert (
        coerce_field_value("stock_quantity", "abc123", "https://example.com/p") is None
    )
    assert (
        coerce_field_value("stock_quantity", "1,234", "https://example.com/p") == 1234
    )


@pytest.mark.unit
def test_public_firewall_does_not_route_invalid_barcode_to_sku() -> None:
    data, rejected = public_record_data_for_surface(
        {"barcode": {"bad": "shape"}},
        surface="ecommerce_detail",
        page_url="https://example.com/p",
    )

    assert "sku" not in data
    assert rejected["barcode"] == "empty_after_coercion"


@pytest.mark.unit
def test_merge_variant_rows_keeps_axis_only_rows_without_url_identity() -> None:
    rows = merge_variant_rows(
        [
            {"size": "8", "price": "100"},
            {"size": "9", "price": "100"},
        ]
    )

    assert [row["size"] for row in rows] == ["8", "9"]
    assert [row["price"] for row in rows] == ["100", "100"]
