"""Product readiness classification for batch summaries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    Product,
    ProductReadiness,
    ProductStatus,
    ProductVersion,
)

CONFLICT_KINDS = {
    DecisionKind.conflicting_sku,
    DecisionKind.conflicting_variant,
    DecisionKind.confirm_product_match,
    DecisionKind.exact_duplicate,
}

INFO_KINDS = {
    DecisionKind.missing_price,
    DecisionKind.no_primary_image,
    DecisionKind.unknown_brand_alias,
    DecisionKind.unknown_color_alias,
    DecisionKind.ambiguous_category,
}


def compute_product_readiness(db: Session, product: Product) -> ProductReadiness:
    if product.status in {ProductStatus.published, ProductStatus.publishing}:
        return ProductReadiness.published

    pending = list(
        db.scalars(
            select(Decision).where(
                Decision.product_id == product.id,
                Decision.status == DecisionStatus.pending,
            )
        ).all()
    )

    if any(d.kind in CONFLICT_KINDS for d in pending):
        return ProductReadiness.has_conflicts

    version = (
        db.get(ProductVersion, product.current_version_id) if product.current_version_id else None
    )
    if version and version.blockers:
        block_kinds = {b.get("kind") for b in version.blockers if isinstance(b, dict)}
        if block_kinds & {"missing_price", "no_primary_image", "missing_field", "invalid_price", "invalid_stock"}:
            return ProductReadiness.needs_information

    if any(d.kind in INFO_KINDS for d in pending):
        return ProductReadiness.needs_information

    if pending:
        # Other pending reviews (suspicious price, unsupported claim, accept_enrichment)
        if product.status == ProductStatus.ready and not pending:
            return ProductReadiness.ready_to_publish
        return ProductReadiness.needs_information

    if product.status == ProductStatus.ready:
        return ProductReadiness.ready_to_publish

    if product.status == ProductStatus.needs_review:
        return ProductReadiness.needs_information

    return ProductReadiness.needs_information


def refresh_product_readiness(db: Session, product: Product) -> ProductReadiness:
    readiness = compute_product_readiness(db, product)
    product.readiness = readiness
    return readiness


def next_action_for_product(db: Session, product: Product) -> str:
    readiness = product.readiness or compute_product_readiness(db, product)
    pending = list(
        db.scalars(
            select(Decision).where(
                Decision.product_id == product.id,
                Decision.status == DecisionStatus.pending,
            )
        ).all()
    )
    if not pending and readiness == ProductReadiness.ready_to_publish:
        return "Select for publication"
    if pending:
        kind = pending[0].kind
        action_map = {
            DecisionKind.missing_price: "Enter price",
            DecisionKind.no_primary_image: "Choose or upload image",
            DecisionKind.conflicting_sku: "Compare records",
            DecisionKind.conflicting_variant: "Choose correct variant",
            DecisionKind.confirm_product_match: "Confirm product match",
            DecisionKind.accept_enrichment: "Accept correction",
            DecisionKind.unknown_brand_alias: "Enter brand",
            DecisionKind.unknown_color_alias: "Enter color",
            DecisionKind.ambiguous_category: "Choose category",
            DecisionKind.suspicious_price: "Review price",
            DecisionKind.unsupported_claim: "Review description",
            DecisionKind.exact_duplicate: "Compare records",
        }
        return action_map.get(kind, "Review issue")
    if readiness == ProductReadiness.published:
        return "View in store" if product.verification_passed else "Retry verification"
    return "Continue with available data"
