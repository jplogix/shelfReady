"""Human-readable labels for supplier and listing fields."""

from __future__ import annotations

FIELD_LABELS: dict[str, str] = {
    "sku": "Supplier SKU",
    "title": "Title",
    "description": "Description",
    "brand": "Brand",
    "color": "Color",
    "category": "Category",
    "product_type": "Product type",
    "price": "Price",
    "currency": "Currency",
    "stock": "Stock",
    "upc": "UPC",
    "gtin": "GTIN",
    "ean": "EAN",
    "mpn": "MPN",
    "model": "Model",
    "size": "Size",
    "pack_quantity": "Pack quantity",
    "image_filename": "Supplier image file",
}


def field_label(field: str) -> str:
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    return field.replace("_", " ").strip().capitalize()
