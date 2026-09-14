"""Catalog normalization helpers. Unknown mappings escalate — never invent certainty."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


SEED_BRAND_ALIASES: dict[str, str] = {
    "GUCCI": "Gucci",
    "gucci": "Gucci",
    "Gucci Eyewear": "Gucci",
    "NORTHWIND CO": "Northwind",
    "Northwind Co.": "Northwind",
    "northwind": "Northwind",
    "AURORA SUPPLY": "Aurora",
    "Aurora Goods": "Aurora",
    "Tide": "Tide",
    "Coca-Cola": "Coca-Cola",
    "Crest": "Crest",
    "Bounty": "Bounty",
    "Head & Shoulders": "Head & Shoulders",
    "CleanCo": "CleanCo",
    "Old Spice": "Old Spice",
    "Demo Co": "Demo Co",
    "SEIKO": "Seiko",
    "Seiko": "Seiko",
    "seiko": "Seiko",
}

SEED_COLOR_ALIASES: dict[str, list[str]] = {
    "BLK/GLD": ["Black", "Gold"],
    "Black Gold": ["Black", "Gold"],
    "Bk-Gd": ["Black", "Gold"],
    "BLK": ["Black"],
    "Black": ["Black"],
    "NVY": ["Navy"],
    "Navy Blue": ["Navy"],
    "WHT": ["White"],
    "White": ["White"],
    "Blue": ["Blue"],
    "Green": ["Green"],
    "Red": ["Red"],
}

SEED_CATEGORY_ALIASES: dict[str, str] = {
    "eye wear": "Eyewear",
    "Eye-Wear": "Eyewear",
    "Bags & Luggage": "Bags",
    "bag": "Bags",
    "apparel": "Apparel",
    "Home Goods": "Home",
    "Beverages": "Beverages",
    "Personal Care": "Personal Care",
    "Household": "Household",
    "Watches": "Watches",
    "watches": "Watches",
}

SEED_TYPE_ALIASES: dict[str, str] = {
    "sunglasses": "Sunglasses",
    "Sun Glasses": "Sunglasses",
    "tote": "Tote Bag",
    "hoodie": "Hoodie",
    "watch": "Watch",
    "Watch": "Watch",
}


@dataclass
class NormResult:
    original: str
    normalized: str | list[str] | None
    known: bool
    needs_decision: bool


def clean_whitespace(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_brand(
    value: str | None,
    active_rules: Iterable[tuple[str, str]] | None = None,
) -> NormResult:
    original = clean_whitespace(value)
    if not original:
        return NormResult(original="", normalized=None, known=False, needs_decision=False)
    rule_map = {k.lower(): v for k, v in SEED_BRAND_ALIASES.items()}
    if active_rules:
        for src, tgt in active_rules:
            rule_map[src.lower()] = tgt
    key = original.lower()
    if key in rule_map or original in SEED_BRAND_ALIASES:
        target = rule_map.get(key) or SEED_BRAND_ALIASES.get(original)
        return NormResult(original=original, normalized=target, known=True, needs_decision=False)
    # Title-case exact match pass-through is known only if already canonical
    for canon in set(SEED_BRAND_ALIASES.values()):
        if original.lower() == canon.lower():
            return NormResult(original=original, normalized=canon, known=True, needs_decision=False)
    return NormResult(original=original, normalized=None, known=False, needs_decision=True)


def normalize_colors(
    value: str | None,
    active_rules: Iterable[tuple[str, str]] | None = None,
) -> NormResult:
    original = clean_whitespace(value)
    if not original:
        return NormResult(original="", normalized=[], known=True, needs_decision=False)
    if original in SEED_COLOR_ALIASES:
        return NormResult(
            original=original,
            normalized=list(SEED_COLOR_ALIASES[original]),
            known=True,
            needs_decision=False,
        )
    if active_rules:
        for src, tgt in active_rules:
            if src.lower() == original.lower():
                families = [p.strip() for p in tgt.split(",") if p.strip()]
                return NormResult(original=original, normalized=families, known=True, needs_decision=False)
    return NormResult(original=original, normalized=None, known=False, needs_decision=True)


def normalize_category(value: str | None) -> NormResult:
    original = clean_whitespace(value)
    if not original:
        return NormResult(original="", normalized=None, known=False, needs_decision=True)
    for src, tgt in SEED_CATEGORY_ALIASES.items():
        if original.lower() == src.lower():
            return NormResult(original=original, normalized=tgt, known=True, needs_decision=False)
    for canon in set(SEED_CATEGORY_ALIASES.values()):
        if original.lower() == canon.lower():
            return NormResult(original=original, normalized=canon, known=True, needs_decision=False)
    return NormResult(original=original, normalized=None, known=False, needs_decision=True)


def normalize_type(value: str | None) -> NormResult:
    original = clean_whitespace(value)
    if not original:
        return NormResult(original="", normalized=None, known=False, needs_decision=False)
    for src, tgt in SEED_TYPE_ALIASES.items():
        if original.lower() == src.lower():
            return NormResult(original=original, normalized=tgt, known=True, needs_decision=False)
    return NormResult(original=original, normalized=original, known=True, needs_decision=False)


UNSUPPORTED_CLAIM_PATTERNS = [
    re.compile(r"\bauthentic\b", re.I),
    re.compile(r"\bcertified\b", re.I),
    re.compile(r"\b100%\s*uv\b", re.I),
    re.compile(r"\bdoctor\s*recommended\b", re.I),
    re.compile(r"\boriginal\s*gucci\b", re.I),
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"system\s*prompt", re.I),
]


def find_unsupported_claims(text: str | None) -> list[str]:
    if not text:
        return []
    hits: list[str] = []
    for pat in UNSUPPORTED_CLAIM_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits
