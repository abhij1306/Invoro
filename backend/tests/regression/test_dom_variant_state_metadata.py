from __future__ import annotations

import pytest

from app.services.extract.detail.variants import dom_extraction


@pytest.mark.regression
def test_state_axis_metadata_uses_cleaned_option_key() -> None:
    axis_metadata = {"Medium": {"selected": True}}

    dom_extraction._merge_state_axis_metadata(
        axis_metadata,
        {"  Medium  ": {"variant_id": "variant-2", "url": "/variant-2"}},
    )

    assert axis_metadata == {
        "Medium": {
            "selected": True,
            "variant_id": "variant-2",
            "url": "/variant-2",
        }
    }
