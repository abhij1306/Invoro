from __future__ import annotations

from .test_normalizers import *  # noqa: F403


@pytest.mark.unit
def test_normalize_variant_record_does_not_invent_color_size_cross_product() -> None:
    record = {
        "color": "Cloud White / Core White / Green",
        "variants": [
            {
                "size": "4",
                "sku": "M20324_530",
                "availability": "in_stock",
                "option_values": {"size": "4"},
            },
            {
                "size": "4.5",
                "sku": "M20324_540",
                "availability": "out_of_stock",
                "option_values": {"size": "4.5"},
            },
            {
                "color": "Cloud White / Core White / Green",
                "url": "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
                "option_values": {"color": "Cloud White / Core White / Green"},
            },
            {
                "color": "Cloud White / Core Black / Green",
                "url": "https://www.adidas.com/us/stan-smith-shoes/M20325.html",
                "option_values": {"color": "Cloud White / Core Black / Green"},
            },
        ],
    }

    normalize_variant_record(record)

    assert all(
        not (variant.get("size") and variant.get("color"))
        for variant in record["variants"]
    )
    assert record.get("variant_count") == 4
    sizes = {
        variant.get("size") for variant in record["variants"] if variant.get("size")
    }
    assert sizes == {"4", "4.5"}
    color_only_values = {
        variant.get("color")
        for variant in record["variants"]
        if variant.get("color") and not variant.get("size")
    }
    assert color_only_values == {
        "Cloud White / Core White / Green",
        "Cloud White / Core Black / Green",
    }

@pytest.mark.unit
def test_normalize_variant_record_drops_numeric_shade_code_size_duplicate() -> None:
    record = {
        "title": "Colorful Eyeshadow",
        "variants": [
            {
                "sku": "2820108",
                "size": "209",
                "color": "209 Mocha Latte",
                "image_url": "https://www.sephora.com/productimages/sku/s2820108-main-hero.jpg",
            },
            {
                "sku": "2819449",
                "size": "601",
                "color": "601 Silver Storm",
                "image_url": "https://www.sephora.com/productimages/sku/s2819449-main-hero.jpg",
            },
        ],
    }

    normalize_variant_record(record)

    assert record["variant_count"] == 2
    assert [variant.get("color") for variant in record["variants"]] == [
        "209 Mocha Latte",
        "601 Silver Storm",
    ]
    assert all("size" not in variant for variant in record["variants"])

@pytest.mark.unit
def test_normalize_variant_record_keeps_parent_scalar_size_without_variants() -> None:
    record = {
        "title": "Colorful Eyeshadow",
        "size": "0.035 oz / 0.99 g",
        "color": "209 Mocha Latte - soft mocha brown matte",
    }

    normalize_variant_record(record)

    assert record["size"] == "0.035 oz / 0.99 g"
    assert record["color"] == "209 Mocha Latte - soft mocha brown matte"
