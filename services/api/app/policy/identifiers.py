"""GTIN/UPC/EAN validation and normalization (structure only, not product identity)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class IdentifierValidation:
    raw: str
    normalized: str | None
    valid: bool
    kind: str | None  # gtin8|gtin12|gtin13|gtin14|invalid
    reason: str | None = None


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _check_digit(body: str) -> int:
    """GS1 mod-10 check digit for GTIN body (without check digit)."""
    total = 0
    rev = body[::-1]
    for i, ch in enumerate(rev):
        n = int(ch)
        total += n * 3 if i % 2 == 0 else n
    return (10 - (total % 10)) % 10


def validate_gtin(value: str | None) -> IdentifierValidation:
    raw = (value or "").strip()
    if not raw:
        return IdentifierValidation(raw="", normalized=None, valid=False, kind=None, reason="empty")

    digits = _digits_only(raw)
    if not digits:
        return IdentifierValidation(raw=raw, normalized=None, valid=False, kind=None, reason="no_digits")

    length_map = {8: "gtin8", 12: "gtin12", 13: "gtin13", 14: "gtin14"}
    if len(digits) not in length_map:
        return IdentifierValidation(
            raw=raw,
            normalized=digits,
            valid=False,
            kind="invalid",
            reason=f"unsupported_length_{len(digits)}",
        )

    body, check = digits[:-1], int(digits[-1])
    expected = _check_digit(body)
    if check != expected:
        return IdentifierValidation(
            raw=raw,
            normalized=digits,
            valid=False,
            kind="invalid",
            reason="check_digit_mismatch",
        )

    return IdentifierValidation(raw=raw, normalized=digits, valid=True, kind=length_map[len(digits)])


def pick_lookup_identifier(mapped: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (field_name, raw_value) for the best available identifier."""
    for field in ("gtin", "upc", "ean"):
        val = mapped.get(field)
        if val and str(val).strip():
            return field, str(val).strip()
    return None, None


def normalize_lookup_query(raw: str) -> str:
    """Normalized query key preserving leading zeros as digits string."""
    return _digits_only(raw)
