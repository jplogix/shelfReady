"""Watch specification fields stored on product versions. Units stay distinct."""

from __future__ import annotations

import re
from typing import Any

WATCH_SPEC_FIELDS = (
    "manufacturer_reference",
    "collection",
    "movement_type",
    "caliber",
    "power_reserve",
    "case_material",
    "case_diameter",
    "case_thickness",
    "lug_to_lug",
    "lug_width",
    "crystal",
    "bracelet_material",
    "dial_color",
    "water_resistance",
    "weight",
)

PUBLIC_SPEC_ORDER = WATCH_SPEC_FIELDS

MANUFACTURER_WATER_RESISTANCE_NOTE = (
    "Manufacturer water-resistance wording only. Not a diving or swimming claim."
)


def normalize_model_reference(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", "", str(value).strip().upper())
    text = text.replace("-", "")
    if not text:
        return None
    return text


def model_token_in_asset(model: str, asset_name: str) -> bool:
    """True when the asset name/URL contains the exact model token (SRPD55 matches SRPD55K1, not SRPD5)."""
    token = normalize_model_reference(model)
    hay = (asset_name or "").upper()
    if not token or len(token) < 5:
        return False
    return bool(re.search(rf"{re.escape(token)}(?:K1)?(?:[_./-]|$)", hay))


def normalize_water_resistance(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    compact = re.sub(r"\s+", "", text.lower())
    if compact in {"10bar", "10-bar"}:
        return "10 bar"
    return text


def copy_watch_fields(source: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in WATCH_SPEC_FIELDS:
        if field in source and source[field] not in (None, ""):
            out[field] = source[field]
    if out.get("water_resistance"):
        out["water_resistance"] = normalize_water_resistance(str(out["water_resistance"]))
    return out


def specification_rows(proposed: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for field in PUBLIC_SPEC_ORDER:
        value = proposed.get(field)
        if value in (None, "", []):
            continue
        if field == "dial_color" and (proposed.get("dial_color_provenance") != "manufacturer_page"):
            continue
        rows.append({"field": field, "value": str(value)})
    return rows
