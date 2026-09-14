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
    "manufacturer_reference": "Manufacturer reference",
    "collection": "Collection",
    "movement_type": "Movement type",
    "caliber": "Caliber",
    "power_reserve": "Power reserve",
    "case_material": "Case material",
    "case_diameter": "Case diameter",
    "case_thickness": "Case thickness",
    "lug_to_lug": "Lug-to-lug length",
    "lug_width": "Lug width",
    "crystal": "Crystal",
    "bracelet_material": "Bracelet / strap material",
    "dial_color": "Dial color",
    "water_resistance": "Water-resistance rating",
    "weight": "Weight",
    "primary_image": "Product photo",
    "demo_scenario": "Demo scenario",
}


def field_label(field: str) -> str:
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    return field.replace("_", " ").strip().capitalize()
