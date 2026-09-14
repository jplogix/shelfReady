"""Public storefront serialization: approved browsing fields and read-only provenance."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ListingAssessmentOut,
    ListingCorrectionOut,
    ListingEvidenceOut,
    ListingFieldOut,
    ListingProvenanceOut,
    StoreImageOut,
    StoreProductOut,
)
from app.policy.field_labels import field_label
from app.config import get_settings
from app.db.models import (
    EvidenceAcceptance,
    FieldEvidence,
    Product,
    ProductVersion,
    StoreProduct,
)
from app.services.demo_catalog import is_public_demo_sku

PUBLIC_ORIGINAL_FIELDS = (
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
    "upc",
    "gtin",
    "ean",
    "mpn",
    "model",
    "size",
    "manufacturer_reference",
    "collection",
    "caliber",
    "movement_type",
    "power_reserve",
    "case_material",
    "case_diameter",
    "case_thickness",
    "lug_to_lug",
    "lug_width",
    "crystal",
    "water_resistance",
    "weight",
)

SKIP_CORRECTION_FIELDS = {
    "image_filename",
    "images",
    "available",
    "brand_original",
    "category_original",
    "color_label",
    "identifier_raw",
    "identifier_normalized",
    "identifier_valid",
    "demo_scenario",
    "primary_image_id",
    "water_resistance_note",
}


def _same_value(left: Any, right: Any) -> bool:
    if left == right:
        return True
    if left in (None, "") and right in (None, "", []):
        return True
    if right in (None, "") and left in (None, "", []):
        return True
    return str(left) == str(right)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def list_public_store_products(db: Session) -> list[StoreProduct]:
    """Shop grid: curated demonstration listings only. Stress-test rows stay off the public catalog."""
    rows = list(db.scalars(select(StoreProduct).order_by(StoreProduct.title)).all())
    visible: list[StoreProduct] = []
    for row in rows:
        product = db.get(Product, row.product_id)
        sku = (product.supplier_sku or product.sku) if product else row.variant_sku
        if not is_public_demo_sku(sku):
            continue
        if "CONFLICT" in (row.title or ""):
            continue
        visible.append(row)
    return visible


def public_images(store_product: StoreProduct) -> list[StoreImageOut]:
    images: list[StoreImageOut] = []
    for img in store_product.images or []:
        if not isinstance(img, dict) or not img.get("path"):
            continue
        images.append(
            StoreImageOut(
                path=str(img["path"]),
                alt=img.get("alt") or store_product.title,
                is_primary=bool(img.get("is_primary")),
                source_kind=img.get("source_kind"),
                usage_permission=img.get("usage_permission"),
                suitability=img.get("suitability"),
                caption=img.get("caption") or None,
            )
        )
    return images


def _primary_image(store_product: StoreProduct) -> StoreImageOut | None:
    rows = public_images(store_product)
    return next((img for img in rows if img.is_primary), rows[0] if rows else None)


def to_public_store_product(store_product: StoreProduct) -> StoreProductOut:
    primary = _primary_image(store_product)
    specs = []
    if isinstance(store_product.seo, dict):
        raw_specs = store_product.seo.get("specifications") or []
        if isinstance(raw_specs, list):
            specs = [row for row in raw_specs if isinstance(row, dict) and row.get("value")]
    return StoreProductOut(
        id=store_product.id,
        slug=store_product.slug,
        title=store_product.title,
        description=store_product.description,
        brand=store_product.brand,
        price=store_product.price,
        currency=store_product.currency,
        stock=store_product.stock,
        available=store_product.available,
        primary_image_path=store_product.primary_image_path,
        images=public_images(store_product),
        sku=store_product.variant_sku,
        image_caption=primary.caption if primary else None,
        image_suitability=primary.suitability if primary else None,
        specifications=[{"field": r.get("field", ""), "value": r.get("value", "")} for r in specs],
        collection=(store_product.seo or {}).get("collection") if isinstance(store_product.seo, dict) else None,
    )


def _public_assessment(raw: dict[str, Any] | None) -> ListingAssessmentOut | None:
    if not raw:
        return None
    agreements = []
    for item in raw.get("attribute_agreements") or []:
        if not isinstance(item, dict):
            continue
        agreements.append(
            {
                "field_name": item.get("field_name"),
                "supplier_value": item.get("supplier_value"),
                "evidence_value": item.get("evidence_value"),
            }
        )
    conflicts = []
    for item in raw.get("attribute_conflicts") or []:
        if not isinstance(item, dict):
            continue
        conflicts.append(
            {
                "field_name": item.get("field_name"),
                "supplier_value": item.get("supplier_value"),
                "evidence_value": item.get("evidence_value"),
            }
        )
    explanation = raw.get("explanation")
    match_outcome = raw.get("match_outcome")
    if not explanation or not match_outcome:
        return None
    return ListingAssessmentOut(
        match_outcome=str(match_outcome),
        explanation=str(explanation),
        recommended_action=raw.get("recommended_action"),
        agreements=agreements,
        conflicts=conflicts,
    )


def listing_provenance(db: Session, store_product: StoreProduct) -> ListingProvenanceOut:
    settings = get_settings()
    product = db.get(Product, store_product.product_id)
    version: ProductVersion | None = None
    if product and product.approved_version_id:
        version = db.get(ProductVersion, product.approved_version_id)
    if product and version is None and product.current_version_id:
        version = db.get(ProductVersion, product.current_version_id)

    original = dict(version.original) if version and version.original else {}
    original_row = {key: original.get(key) for key in PUBLIC_ORIGINAL_FIELDS if key in original and key != "demo_scenario"}

    corrections: list[ListingCorrectionOut] = []
    for diff in version.diffs if version and version.diffs else []:
        if not isinstance(diff, dict):
            continue
        field = str(diff.get("field") or "")
        if not field or field in SKIP_CORRECTION_FIELDS:
            continue
        if _same_value(diff.get("original"), diff.get("proposed")):
            continue
        corrections.append(
            ListingCorrectionOut(
                field=field,
                label=field_label(field),
                original=diff.get("original"),
                accepted=diff.get("proposed"),
            )
        )

    evidence_rows = []
    if product:
        rows = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product.id)).all()
        corrected = {c.field for c in corrections}
        for row in rows:
            accepted = row.acceptance_status == EvidenceAcceptance.accepted
            supports_listing = row.field_name in corrected
            if not accepted and not supports_listing:
                continue
            proposed = row.proposed_value
            if row.field_name == "primary_image":
                proposed = "Retrieved manufacturer photograph"
            evidence_rows.append(
                ListingEvidenceOut(
                    field_name=row.field_name,
                    label=field_label(row.field_name),
                    original_supplier_value=row.original_supplier_value,
                    proposed_value=proposed,
                    source_provider=row.source_provider,
                    source_url=row.source_url,
                    match_outcome=str(_enum_value(row.match_outcome)),
                    match_explanation=row.match_explanation,
                    is_replay=bool(row.is_replay),
                )
            )

    assessment_raw = (version.provenance or {}).get("assessment") if version else None
    stored_mode = (version.provenance or {}).get("manufacturer_source") if version else {}
    if not isinstance(stored_mode, dict):
        stored_mode = {}
    agent = stored_mode.get("agent_mode") or settings.agent_mode
    lookup = stored_mode.get("lookup_mode") or settings.lookup_provider
    retrieval = stored_mode.get("retrieval_mode")
    if agent == "replay":
        label = "Fixture replay · replay lookup" if lookup == "replay" else "Fixture replay · live lookup"
    elif lookup == "replay":
        label = "Live agent · replay lookup"
    else:
        label = "Live agent · live lookup"
    if retrieval:
        label = f"{label} · manufacturer source {retrieval}"

    photo_added = any(row.field_name == "primary_image" for row in evidence_rows)
    spec_fields = {
        "caliber",
        "movement_type",
        "case_diameter",
        "water_resistance",
        "manufacturer_reference",
        "collection",
        "power_reserve",
        "crystal",
    }
    specs_completed = sum(1 for c in corrections if c.field in spec_fields)
    if photo_added and specs_completed:
        outcome = "Added a product photo and completed supported specifications."
    elif photo_added:
        outcome = "Added a product photo."
    elif specs_completed:
        outcome = f"Completed {specs_completed} supported specification{'s' if specs_completed != 1 else ''}."
    elif corrections:
        outcome = f"Applied {len(corrections)} accepted improvement{'s' if len(corrections) != 1 else ''}."
    else:
        outcome = "Published listing matches the accepted supplier facts."

    original_fields = [
        ListingFieldOut(field=key, label=field_label(key), value=value)
        for key, value in original_row.items()
    ]
    primary = _primary_image(store_product)

    return ListingProvenanceOut(
        slug=store_product.slug,
        title=store_product.title,
        preparation_label=label,
        agent_mode=agent,
        lookup_mode=lookup,
        original_row=original_row,
        original_fields=original_fields,
        corrections=corrections,
        evidence=evidence_rows,
        assessment=_public_assessment(assessment_raw if isinstance(assessment_raw, dict) else None),
        image_caption=primary.caption if primary else None,
        image_suitability=primary.suitability if primary else None,
        outcome_summary=outcome,
    )
