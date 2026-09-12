"""Batch count reconciliation and product list summaries."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Batch,
    Decision,
    DecisionStatus,
    FieldEvidence,
    ImportRow,
    MatchOutcome,
    Product,
    ProductReadiness,
    ProductStatus,
    ProductVersion,
    StoreProduct,
)
from app.policy.readiness import compute_product_readiness, next_action_for_product, refresh_product_readiness


def recompute_batch_counts(db: Session, batch: Batch) -> dict[str, Any]:
    products = db.scalars(select(Product).where(Product.batch_id == batch.id)).all()
    source_rows = db.scalar(
        select(func.count()).select_from(ImportRow).where(ImportRow.batch_id == batch.id)
    ) or 0

    counts: dict[str, Any] = {
        "source_rows": int(source_rows),
        "products": len(products),
        "ready_to_publish": 0,
        "needs_information": 0,
        "has_conflicts": 0,
        "published": 0,
        "verified": 0,
        "verification_failed": 0,
        "issues": 0,
        "products_with_issues": 0,
        "fields_corrected": 0,
    }

    fields_corrected = 0
    for p in products:
        refresh_product_readiness(db, p)
        readiness = p.readiness or compute_product_readiness(db, p)
        if p.status == ProductStatus.published:
            counts["published"] += 1
            if p.verification_passed:
                counts["verified"] += 1
        elif p.status == ProductStatus.verification_failed:
            counts["published"] += 1
            counts["verification_failed"] += 1
        elif readiness == ProductReadiness.ready_to_publish:
            counts["ready_to_publish"] += 1
        elif readiness == ProductReadiness.has_conflicts:
            counts["has_conflicts"] += 1
        else:
            counts["needs_information"] += 1

        if p.current_version_id:
            v = db.get(ProductVersion, p.current_version_id)
            if v and v.diffs:
                fields_corrected += len(v.diffs)

    pending = db.scalars(
        select(Decision).where(
            Decision.batch_id == batch.id,
            Decision.status == DecisionStatus.pending,
        )
    ).all()
    counts["issues"] = len(pending)
    counts["products_with_issues"] = len({d.product_id for d in pending if d.product_id})
    counts["fields_corrected"] = fields_corrected

    batch.counts = counts
    return counts


def enrichment_summary(db: Session, product_id: uuid.UUID) -> str:
    rows = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product_id)).all()
    if not rows:
        return "No lookup run"
    outcomes = {r.match_outcome for r in rows}
    if MatchOutcome.matching_evidence in outcomes:
        enriched = sum(1 for r in rows if r.proposed_value is not None)
        return f"{enriched} fields from barcode evidence"
    if MatchOutcome.conflicting_evidence in outcomes:
        return "Variant conflict detected"
    if MatchOutcome.invalid_identifier in outcomes:
        return "Invalid identifier"
    if MatchOutcome.lookup_unavailable in outcomes:
        return "Lookup unavailable"
    if MatchOutcome.no_match in outcomes:
        return "No barcode match"
    return "Evidence recorded"


def product_list_item(db: Session, product: Product) -> dict[str, Any]:
    version = (
        db.get(ProductVersion, product.current_version_id) if product.current_version_id else None
    )
    proposed = version.proposed if version else {}
    thumb = None
    if product.images:
        primary = next((i for i in product.images if i.is_primary), product.images[0])
        thumb = primary.derivative_path or primary.original_path
    pending_count = db.scalar(
        select(func.count())
        .select_from(Decision)
        .where(Decision.product_id == product.id, Decision.status == DecisionStatus.pending)
    )
    readiness = product.readiness or compute_product_readiness(db, product)
    return {
        "id": product.id,
        "sku": product.sku,
        "supplier_sku": product.supplier_sku or product.sku.split("__row")[0],
        "title": proposed.get("title") or product.sku,
        "price": proposed.get("price"),
        "currency": proposed.get("currency") or "USD",
        "status": product.status.value,
        "readiness": readiness.value if readiness else None,
        "verification_passed": product.verification_passed,
        "current_version_id": product.current_version_id,
        "approved_version_id": product.approved_version_id,
        "store_product_id": product.store_product_id,
        "store_slug": product.store_slug,
        "thumbnail": thumb,
        "issue_count": int(pending_count or 0),
        "enrichment_summary": enrichment_summary(db, product.id),
        "next_action": next_action_for_product(db, product),
        "is_publishable": version.is_publishable if version else False,
    }
