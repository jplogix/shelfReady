"""Image suitability and demonstration-image metadata."""

import pytest

from app.policy.images import lookup_image_meta, suitability_for
from app.storage.local import LocalStorage, StorageError


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


def test_invalid_bytes_are_not_stored(tmp_path):
    storage = LocalStorage(root=tmp_path)
    with pytest.raises(StorageError, match="decode_failed"):
        storage.save_image(b"not-an-image", filename="x.png")


def test_oversized_payload_is_rejected(tmp_path):
    from app.storage.local import MAX_BYTES

    storage = LocalStorage(root=tmp_path)
    with pytest.raises(StorageError, match="file_too_large"):
        storage.save_image(b"\x00" * (MAX_BYTES + 1), filename="huge.png")
