from __future__ import annotations

from .test_shared_variant_logic import BeautifulSoup, axis_values_are_mislabeled_duplicate, backfill_variants_from_dom_if_missing, extract_variants_from_dom, infer_variant_group_name_from_values, iter_variant_choice_groups, normalized_variant_axis_key, pytest, resolve_variant_group_name, resolve_variants, variant_choice_container_for_input, variant_choice_container_is_overbroad  # fmt: skip
from app.services.extract import variant_choice_collection


@pytest.mark.unit
def test_variant_choice_groups_skip_overbroad_parent_and_keep_fieldsets() -> None:
    soup = BeautifulSoup(
        """
        <div class="page">
          <div id="attribute-accordion" class="accordion">
            <div class="card-body">
              <div class="attr-group-body">
                <fieldset class="attr-group-items">
                  <input
                    type="radio"
                    id="size-size_a_small"
                    name="size"
                    data-attr-displayvalue="Size A - Small"
                  />
                  <label for="size-size_a_small">
                    <span class="sr-only">View this product in: Size</span>
                    <span>Size A - Small</span>
                  </label>
                  <input
                    type="radio"
                    id="size-size_b_medium"
                    name="size"
                    data-attr-displayvalue="Size B - Medium"
                  />
                  <label for="size-size_b_medium">
                    <span class="sr-only">View this product in: Size</span>
                    <span>Size B - Medium</span>
                  </label>
                </fieldset>
              </div>
            </div>
            <div class="card-body">
              <div class="attr-group-body">
                <fieldset class="attr-group-items">
                  <input
                    type="radio"
                    id="backSupport-basic_back_support"
                    name="backSupport"
                    data-attr-displayvalue="Basic Back Support"
                  />
                  <label for="backSupport-basic_back_support">
                    <span class="sr-only">View this product in: Back Support</span>
                    <span>Basic Back Support</span>
                  </label>
                  <input
                    type="radio"
                    id="backSupport-adjustable_lumbar_support"
                    name="backSupport"
                    data-attr-displayvalue="Adjustable Lumbar Support"
                  />
                  <label for="backSupport-adjustable_lumbar_support">
                    <span class="sr-only">View this product in: Back Support</span>
                    <span>Adjustable Lumbar Support</span>
                  </label>
                </fieldset>
              </div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    groups = list(iter_variant_choice_groups(soup))

    assert [
        normalized_variant_axis_key(resolve_variant_group_name(group))
        for group in groups
    ] == [
        "size",
        "back_support",
    ]
    assert not any(group.get("id") == "attribute-accordion" for group in groups)


@pytest.mark.unit
def test_variant_choice_groups_ignore_navigation_link_lists() -> None:
    soup = BeautifulSoup(
        """
        <main>
          <fieldset>
            <legend>Size</legend>
            <button>4</button>
            <button>4.5</button>
          </fieldset>
        </main>
        <nav>
          <ul>
            <li><a href="/us/bags">Bags & Backpacks</a></li>
            <li><a href="/us/soccer">Soccer</a></li>
            <li><a href="/us/tennis">Tennis</a></li>
          </ul>
        </nav>
        """,
        "html.parser",
    )

    groups = list(iter_variant_choice_groups(soup))

    assert len(groups) == 1
    assert resolve_variant_group_name(groups[0]) == "Size"


@pytest.mark.unit
def test_variant_choice_groups_collect_button_container_not_buttons() -> None:
    soup = BeautifulSoup(
        """
        <section class="size-options" aria-label="Size">
          <button class="size-option" data-variant="small">Small</button>
          <button class="size-option" data-variant="large">Large</button>
        </section>
        """,
        "html.parser",
    )

    groups = iter_variant_choice_groups(soup)

    assert len(groups) == 1
    assert groups[0].name == "section"
    assert len(groups[0].select("button")) == 2


@pytest.mark.unit
def test_narrow_button_pass_does_not_scan_parent_subtrees() -> None:
    class FakeNode:
        name = "button"

        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.attrs = {"class": ["size-option"], "data-variant": "size"}

        def get(self, key: str):  # type: ignore[no-untyped-def]
            return self.attrs.get(key)

    class FakeParent(FakeNode):
        name = "section"

        def __init__(self) -> None:
            super().__init__()
            self.attrs = {"class": ["size-options"], "aria-label": "Size"}

        def select(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("narrow button pass must not scan parent subtrees")

    parent = FakeParent()
    nodes = [FakeNode(parent), FakeNode(parent)]

    groups: list[object] = []
    reached_limit = variant_choice_collection._add_button_choice_groups(
        type("FakeSoup", (), {"select": lambda self, selector: nodes})(),
        groups,
        set(),
    )

    assert reached_limit is False
    assert groups == [parent]


@pytest.mark.unit
def test_input_choice_scan_respects_global_candidate_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = [object() for _ in range(10)]
    visited: list[object] = []
    monkeypatch.setattr(variant_choice_collection, "VARIANT_CHOICE_INPUT_SCAN_LIMIT", 3)
    monkeypatch.setattr(
        variant_choice_collection,
        "variant_node_in_noise_context",
        lambda node: False,
    )

    def _candidate(node):  # type: ignore[no-untyped-def]
        visited.append(node)
        return None

    monkeypatch.setattr(
        variant_choice_collection,
        "variant_choice_container_for_input",
        _candidate,
    )

    groups: list[object] = []
    variant_choice_collection._add_input_choice_groups(
        type("FakeSoup", (), {"select": lambda self, selector: nodes})(),
        groups,
        set(),
    )

    assert visited == nodes[:3]


@pytest.mark.unit
def test_input_choice_parent_walk_respects_depth_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeNode:
        name = "div"

        def __init__(self, parent=None) -> None:
            self.parent = parent

        def get(self, key: str):  # type: ignore[no-untyped-def]
            return "radio" if key == "type" else None

    parent = None
    for _ in range(20):
        parent = FakeNode(parent)
    node = FakeNode(parent)
    visited: list[object] = []

    def _ineligible(candidate):  # type: ignore[no-untyped-def]
        visited.append(candidate)
        return False

    monkeypatch.setattr(
        variant_choice_collection,
        "_input_parent_is_eligible",
        _ineligible,
    )

    assert variant_choice_container_for_input(node) is None
    assert len(visited) == variant_choice_collection.VARIANT_SWATCH_PARENT_DEPTH


@pytest.mark.unit
def test_variant_choice_groups_reuse_cached_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def _stage(soup, groups, seen):  # type: ignore[no-untyped-def]
        nonlocal calls
        del soup, groups, seen
        calls += 1
        return False

    soup = type("FakeSoup", (), {})()
    monkeypatch.setattr(variant_choice_collection, "_add_labeled_role_groups", _stage)
    monkeypatch.setattr(
        variant_choice_collection, "_add_configured_choice_groups", _stage
    )
    monkeypatch.setattr(variant_choice_collection, "_add_input_choice_groups", _stage)
    monkeypatch.setattr(variant_choice_collection, "_add_button_choice_groups", _stage)
    monkeypatch.setattr(
        variant_choice_collection,
        "_add_swatch_choice_groups",
        lambda soup, groups, seen: None,
    )

    assert variant_choice_collection.iter_variant_choice_groups(soup) == []
    assert variant_choice_collection.iter_variant_choice_groups(soup) == []
    assert calls == 4


@pytest.mark.unit
def test_dom_variant_extraction_trusts_size_values_over_color_container_label() -> None:
    soup = BeautifulSoup(
        """
        <main>
          <section class="product-detail">
            <div class="color-selector">
              <button aria-label="M 5 / W 6.5">Visible M5/W6.5</button>
              <button aria-label="M 5.5 / W 7">Visible M5.5/W7</button>
              <button aria-label="M 6 / W 7.5">Visible M6/W7.5</button>
            </div>
          </section>
        </main>
        """,
        "html.parser",
    )

    record = extract_variants_from_dom(
        soup,
        page_url="https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
    )

    assert record["variant_count"] == 3
    assert [row.get("size") for row in record["variants"]] == [
        "M 5 / W 6.5",
        "M 5.5 / W 7",
        "M 6 / W 7.5",
    ]
    assert all("color" not in row for row in record["variants"])


@pytest.mark.unit
def test_dom_variant_extraction_filters_fulfillment_noise_from_color_group() -> None:
    soup = BeautifulSoup(
        """
        <main>
          <fieldset class="color-selector">
            <legend>Color</legend>
            <button aria-label="209 Mocha Latte - soft mocha brown matte"></button>
            <button aria-label="210 Satin Corset - rose gold shimmer"></button>
            <button>Shipping &amp; Returns</button>
            <button>About Auto-Replenish</button>
            <button>Same-Day Delivery FREE with code FREESAME</button>
          </fieldset>
        </main>
        """,
        "html.parser",
    )

    record = extract_variants_from_dom(
        soup,
        page_url="https://www.sephora.com/product/colorful-eyeshadow-P515026",
    )

    assert record["variant_count"] == 2
    assert [row.get("color") for row in record["variants"]] == [
        "209 Mocha Latte - soft mocha brown matte",
        "210 Satin Corset - rose gold shimmer",
    ]
    assert all(set(row) <= {"color", "_validated"} for row in record["variants"])


def testvariant_choice_container_is_overbroad_avoids_css_select_scans() -> None:
    class FakeNode:
        name = "div"

        def find_all(self, name=None, attrs=None, limit=None):  # type: ignore[no-untyped-def]
            if name == "fieldset":
                return [object(), object()]
            return []

        def select(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("slow CSS select path should not run")

    assert variant_choice_container_is_overbroad(FakeNode()) is True


def testvariant_choice_container_for_input_avoids_css_select_scans() -> None:
    class FakeInput:
        name = "input"

        def __init__(
            self,
            attrs: dict[str, str] | None = None,
            *,
            parent=None,
        ) -> None:
            self.attrs = dict(attrs or {})
            self.parent = parent

        def get(self, key: str) -> str | None:
            return self.attrs.get(key)

    class FakeParent:
        name = "div"

        def __init__(self) -> None:
            self.attrs = {"class": ["size-selector"]}
            self.children = [
                FakeInput({"type": "radio", "name": "size"}, parent=self),
                FakeInput({"type": "radio", "name": "size"}, parent=self),
            ]
            self.parent = None

        def get(self, key: str):  # type: ignore[no-untyped-def]
            return self.attrs.get(key)

        def find_all(self, name=None, attrs=None, limit=None):  # type: ignore[no-untyped-def]
            if name == "fieldset":
                return []
            if name == ["input", "button"] or name == ("input", "button"):
                return list(self.children)
            if name == "select":
                return []
            if attrs == {"role": "radiogroup"} or attrs == {"aria-label": True}:
                return []
            return []

        def select(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("slow CSS select path should not run")

    parent = FakeParent()
    node = parent.children[0]

    assert variant_choice_container_for_input(node, axis_name="size") is parent


@pytest.mark.parametrize(
    "value",
    ["10M", "8.5M", "7.5M", "11.5XW", "9W", "9N", "7D", "32A", "34DD", "32x30"],
)
@pytest.mark.unit
def test_unlabeled_numeric_size_values_infer_size_not_color(value: str) -> None:
    """Numeric/size-shaped option values (incl. footwear width codes and
    waist x inseam) classify as size, never color."""
    values = [value, "10M", "11M", "12M"]
    assert infer_variant_group_name_from_values(values) == "size"


@pytest.mark.unit
def test_unlabeled_shoe_size_group_classifies_as_size_not_color() -> None:
    """An unlabeled option group (no accessible axis name) whose values are
    footwear sizes must resolve to a single `size` axis, not `color`.

    Reproduces the Belk React PDP bug where size radio values like 10M / 8.5M
    were defaulted to color, corrupting variants for any site whose size
    radiogroup has no accessible axis name.
    """
    sizes = ["7M", "7.5M", "8M", "8.5M", "9M", "10M", "10.5M", "11M"]
    radios = "".join(
        f'<label for="opt-{s}">{s}'
        f'<button role="radio" id="opt-{s}" value="50500_{s}"></button></label>'
        for s in sizes
    )
    soup = BeautifulSoup(
        f"""
        <main><section class="product-detail">
          <div role="radiogroup" class="grid gap-3">{radios}</div>
        </section></main>
        """,
        "html.parser",
    )

    record = extract_variants_from_dom(
        soup,
        page_url="https://www.example.com/p/sneaker/123.html",
    )

    variants = [row for row in record.get("variants", []) if isinstance(row, dict)]
    assert variants
    assert {row.get("size") for row in variants if row.get("size")} == set(sizes)
    assert all("color" not in row for row in variants)


@pytest.mark.unit
def test_axis_values_are_mislabeled_duplicate_detects_same_axis() -> None:
    """The same value set under two axis names is a mislabeled duplicate."""
    sizes = ["7M", "8M", "9M", "10M"]
    assert axis_values_are_mislabeled_duplicate(sizes, list(sizes)) is True
    # Genuinely independent axes do not overlap.
    assert (
        axis_values_are_mislabeled_duplicate(["Red", "Blue"], ["S", "M", "L"]) is False
    )
    # Empty axes are never duplicates.
    assert axis_values_are_mislabeled_duplicate([], ["S"]) is False


@pytest.mark.unit
def test_resolve_variants_does_not_explode_mislabeled_duplicate_axis() -> None:
    """A single real axis mislabeled as two (color == size value set) must not
    fabricate a Cartesian product."""
    sizes = ["7M", "8M", "9M", "10M"]
    axes = {"size": list(sizes), "color": list(sizes)}
    variants = [
        {"option_values": {"size": s}, "size": s, "sku": f"SKU-{s}"} for s in sizes
    ]

    resolved = resolve_variants(axes, variants)

    assert len(resolved) == len(sizes)
    assert {row.get("size") for row in resolved} == set(sizes)
    assert all(not row.get("color") for row in resolved)


@pytest.mark.unit
def test_single_axis_source_not_exploded_by_mislabeled_dom_axis() -> None:
    """A single-axis (size) source carrying its own transport fields must not be
    exploded into a Cartesian product when the DOM mislabels the same values as
    a second axis."""
    sizes = ["7", "7.5", "8", "8.5", "9", "9.5", "10"]
    record = {
        "variants": [
            {
                "size": s,
                "option_values": {"size": s},
                "sku": f"SKU{i}",
                "barcode": f"0000000001{i:03d}",
                "price": "90.00",
                "availability": "in_stock",
            }
            for i, s in enumerate(sizes)
        ],
        "variant_count": len(sizes),
        "price": "90.00",
        "currency": "USD",
        "availability": "in_stock",
    }
    buttons = "".join(f'<button aria-label="{s}">{s}</button>' for s in sizes)
    soup = BeautifulSoup(
        f"""
        <main><section class="product-detail">
          <div class="color-selector"><span>Color</span>{buttons}</div>
        </section></main>
        """,
        "html.parser",
    )

    backfill_variants_from_dom_if_missing(
        record,
        soup=soup,
        page_url="https://www.example.com/p/shoe/123.html",
    )

    variants = [row for row in record.get("variants", []) if isinstance(row, dict)]
    assert len(variants) == len(sizes)
    assert {row.get("size") for row in variants if row.get("size")} == set(sizes)
    # Barcodes survive; no phantom color×size cross-product rows.
    assert {row.get("barcode") for row in variants if row.get("barcode")} == {
        f"0000000001{i:03d}" for i in range(len(sizes))
    }
    assert all(not row.get("color") for row in variants)
