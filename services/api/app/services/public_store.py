"""Public storefront serialization: approved browsing fields and read-only provenance."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ListingAssessmentOut,
    ListingCorrectionOut,
    ListingEvidenceOut,
    ListingProvenanceOut,
    StoreImageOut,
    StoreProductOut,
)
from app.config import get_settings
from app.db.models import (
    EvidenceAcceptance,
    FieldEvidence,
    Product,
    ProductVersion,
    StoreProduct,
)

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
)

SKIP_CORRECTION_FIELDS = {
    "image_filename",
    "images",
    "available",
    "brand_original",
    "category_original",
    "color_label",
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
            )
        )
    return images


def to_public_store_product(store_product: StoreProduct) -> StoreProductOut:
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
    if product and product.current_version_id:
        version = db.get(ProductVersion, product.current_version_id)

    original = dict(version.original) if version and version.original else {}
    original_row = {key: original.get(key) for key in PUBLIC_ORIGINAL_FIELDS if key in original}

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
            evidence_rows.append(
                ListingEvidenceOut(
                    field_name=row.field_name,
                    original_supplier_value=row.original_supplier_value,
                    proposed_value=row.proposed_value,
                    source_provider=row.source_provider,
                    source_url=row.source_url,
                    match_outcome=str(_enum_value(row.match_outcome)),
                    match_explanation=row.match_explanation,
                    is_replay=bool(row.is_replay),
                )
            )

    assessment_raw = (version.provenance or {}).get("assessment") if version else None
    agent = settings.agent_mode
    lookup = settings.lookup_provider
    if agent == "replay":
        label = "Fixture replay · replay lookup" if lookup == "replay" else "Fixture replay · live lookup"
    elif lookup == "replay":
        label = "Live agent · replay lookup"
    else:
        label = "Live agent · live lookup"

    return ListingProvenanceOut(
        slug=store_product.slug,
        title=store_product.title,
        preparation_label=label,
        agent_mode=agent,
        lookup_mode=lookup,
        original_row=original_row,
        corrections=corrections,
        evidence=evidence_rows,
        assessment=_public_assessment(assessment_raw if isinstance(assessment_raw, dict) else None),
    )
