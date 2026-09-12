"""CSV import and column mapping."""

from __future__ import annotations

import csv
import io
from typing import Any

CANONICAL_FIELDS = [
    "sku",
    "title",
    "description",
    "brand",
    "color",
    "category",
    "product_type",
    "price",
    "currency",
    "stock",
    "image_filename",
    "gtin",
    "upc",
    "ean",
    "mpn",
    "model",
    "size",
    "pack_quantity",
]


FIELD_ALIASES = {
    "sku": ["sku", "item_sku", "product_sku", "id"],
    "title": ["title", "name", "product_name", "product_title"],
    "description": ["description", "desc", "long_description", "product_description"],
    "brand": ["brand", "manufacturer", "brand_name"],
    "color": ["color", "colour", "color_label"],
    "category": ["category", "cat", "product_category"],
    "product_type": ["product_type", "type", "item_type"],
    "price": ["price", "unit_price", "list_price"],
    "currency": ["currency", "curr", "currency_code"],
    "stock": ["stock", "qty", "quantity", "inventory"],
    "image_filename": ["image_filename", "image", "image_file", "primary_image"],
    "gtin": ["gtin", "barcode", "global_trade_item_number"],
    "upc": ["upc", "upc_code", "upc_a"],
    "ean": ["ean", "ean13", "ean_13"],
    "mpn": ["mpn", "manufacturer_part_number", "part_number"],
    "model": ["model", "model_number", "model_no"],
    "size": ["size", "item_size", "variant_size"],
    "pack_quantity": ["pack_quantity", "pack_qty", "pack_size", "units_per_pack"],
}

IDENTIFIER_FIELDS = {"gtin", "upc", "ean"}


def suggest_column_mapping(headers: list[str]) -> dict[str, str | None]:
    normalized = {h: h.strip() for h in headers}
    lower_map = {h.lower().strip(): h for h in headers}
    mapping: dict[str, str | None] = {f: None for f in CANONICAL_FIELDS}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lower_map:
                mapping[field] = lower_map[alias]
                break
        if mapping[field] is None:
            for h in headers:
                if field in h.lower():
                    mapping[field] = normalized[h]
                    break
    return mapping


def parse_csv_bytes(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    headers = [h for h in reader.fieldnames if h is not None]
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({k: (v if v is not None else "") for k, v in row.items() if k is not None})
    return headers, rows


def apply_mapping(raw: dict[str, str], mapping: dict[str, str | None]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, source in mapping.items():
        if source and source in raw:
            val = raw[source]
            if isinstance(val, str):
                val = val.strip()
            # Preserve barcode strings exactly (including leading zeros)
            if field in IDENTIFIER_FIELDS or field in {"mpn", "model", "size", "pack_quantity", "sku"}:
                out[field] = val if val != "" else None
            else:
                out[field] = val if val != "" else None
        else:
            out[field] = None
    return out


def validate_mapped_row(mapped: dict[str, Any], row_number: int) -> tuple[bool, str | None]:
    if not mapped.get("sku"):
        return False, f"Row {row_number}: missing SKU"
    if not mapped.get("title"):
        return False, f"Row {row_number}: missing title"
    return True, None


def row_fingerprint(mapped: dict[str, Any]) -> str:
    parts = [
        str(mapped.get("sku") or ""),
        str(mapped.get("title") or ""),
        str(mapped.get("brand") or ""),
        str(mapped.get("price") or ""),
        str(mapped.get("stock") or ""),
        str(mapped.get("color") or ""),
    ]
    return "|".join(parts)
