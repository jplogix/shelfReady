"""Image suitability and demonstration-image metadata."""

from app.policy.images import lookup_image_meta, suitability_for


def test_demo_illustration_matches_paper_towels():
    meta = lookup_image_meta("demo-paper-towels.png")
    assert meta is not None
    assert meta.source_kind == "fixture_illustration"
    assert meta.usage_permission == "demonstration_only"
    assert suitability_for(meta, "Paper Towels", "Household") == "category_match"


def test_hoodie_fixture_is_not_suitable_for_paper_towels():
    meta = lookup_image_meta("aurora-hoodie.png")
    assert meta is not None
    assert suitability_for(meta, "Paper Towels", "Household") == "category_mismatch"


def test_empty_product_type_is_unclassified_not_a_false_mismatch():
    meta = lookup_image_meta("demo-soda-can.png")
    assert suitability_for(meta, None, None) == "unclassified"
