"""Identifier validation tests."""

from app.policy.identifiers import normalize_lookup_query, pick_lookup_identifier, validate_gtin


def test_leading_zero_barcode_preserved():
    raw = "049000028911"
    v = validate_gtin(raw)
    assert v.valid
    assert v.normalized == "049000028911"
    assert normalize_lookup_query("049000028911") == "049000028911"


def test_invalid_check_digit():
    v = validate_gtin("049000028910")
    assert not v.valid
    assert v.reason == "check_digit_mismatch"


def test_pick_lookup_prefers_gtin():
    mapped = {"upc": "123", "gtin": "049000028911", "ean": None}
    field, val = pick_lookup_identifier(mapped)
    assert field == "gtin"
    assert val == "049000028911"
