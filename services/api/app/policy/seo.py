"""SEO draft helpers — grounded templates only, no fabricated claims."""

from __future__ import annotations

import re
from typing import Any

from slugify import slugify


def build_seo_draft(proposed: dict[str, Any], *, existing_slugs: set[str] | None = None) -> dict[str, Any]:
    brand = (proposed.get("brand") or "").strip()
    title = (proposed.get("title") or "").strip()
    color = proposed.get("color_label") or ""
    product_type = proposed.get("product_type") or ""
    category = proposed.get("category") or ""
    facts = [p for p in [brand, title, color, product_type] if p]
    short = " · ".join(facts[:3]) if facts else title
    page_title = f"{brand} {title}".strip()[:60] if brand else title[:60]
    meta = f"{short}. Available from the ShelfReady demo storefront."[:155]
    base_slug = slugify(f"{brand}-{title}" if brand else title) or "product"
    slug = unique_slug(base_slug, existing_slugs or set())
    alt = f"{brand} {title}".strip() if brand else title
    if color:
        alt = f"{alt} in {color}"
    return {
        "product_title": title,
        "short_description": short,
        "page_title": page_title,
        "meta_description": meta,
        "image_alt": alt,
        "url_slug": slug,
        "source": "generated_grounded",
        "noindex": True,
    }


def unique_slug(base: str, existing: set[str]) -> str:
    candidate = base
    n = 2
    while candidate in existing:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def build_json_ld(
    *,
    name: str,
    description: str | None,
    sku: str,
    brand: str | None,
    price: str,
    currency: str,
    available: bool,
    image_url: str | None,
    canonical_url: str,
) -> dict[str, Any]:
    availability = (
        "https://schema.org/InStock" if available else "https://schema.org/OutOfStock"
    )
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "sku": sku,
        "url": canonical_url,
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": availability,
            "url": canonical_url,
        },
    }
    if description:
        data["description"] = description
    if brand:
        data["brand"] = {"@type": "Brand", "name": brand}
    if image_url:
        data["image"] = [image_url]
    return data


INJECTION_MARKERS = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|system\s*prompt|you\s+are\s+now)",
    re.I,
)


def sanitize_supplier_text(text: str | None) -> str:
    """Treat supplier text as untrusted; strip injection markers for display drafts."""
    if not text:
        return ""
    cleaned = INJECTION_MARKERS.sub("[redacted-untrusted-instruction]", text)
    return cleaned.strip()
