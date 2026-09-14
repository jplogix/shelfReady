"""Publish a small verified demonstration catalog for the public storefront."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.agent.runner import execute_job
from app.api.schemas import DecisionResolve, PublishRequest
from app.db.models import (
    Batch,
    BatchKind,
    Decision,
    DecisionKind,
    DecisionStatus,
    EvidenceAcceptance,
    FieldEvidence,
    Job,
    JobStatus,
    Product,
    ProductReadiness,
    ProductVersion,
    StoreProduct,
)
from app.db.session import SessionLocal
from app.policy.readiness import refresh_product_readiness
from app.services.demo_catalog import PUBLIC_DEMO_SKUS, canonical_sku

logger = logging.getLogger(__name__)

PUBLIC_DEMO_BATCH = "Seiko demonstration catalog"
HOUSEHOLD_DEMO_BATCH = "Household demonstration catalog"
SAFE_BOOTSTRAP_KINDS = {
    DecisionKind.accept_enrichment,
    DecisionKind.unsupported_claim,
    DecisionKind.no_primary_image,
    DecisionKind.unknown_brand_alias,
}
ADVISORY_LOCK = 872401


def ensure_public_storefront() -> None:
    """Idempotent: import, process, and publish ready demo products when the store is empty."""
    if os.environ.get("BOOTSTRAP_STOREFRONT", "1") in {"0", "false", "False"}:
        logger.info("Skipping storefront bootstrap (BOOTSTRAP_STOREFRONT disabled)")
        return

    db = SessionLocal()
    try:
        db.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ADVISORY_LOCK})
        featured = 0
        for row in db.scalars(select(StoreProduct)).all():
            product = db.get(Product, row.product_id)
            sku = (product.supplier_sku or product.sku) if product else row.variant_sku
            if canonical_sku(sku) in PUBLIC_DEMO_SKUS:
                featured += 1
        if featured:
            logger.info("Featured Seiko collection already has %s published products", featured)
            return
        _bootstrap(db)
    except Exception:
        logger.exception("Storefront bootstrap failed; API will still start")
        db.rollback()
    finally:
        try:
            db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK})
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def ready_public_demo_ids(db: Session, batch_id: uuid.UUID) -> list[uuid.UUID]:
    from app.services.batch_metrics import product_list_item

    return [
        p.id
        for p in db.scalars(select(Product).where(Product.batch_id == batch_id)).all()
        if canonical_sku(p.supplier_sku or p.sku) in PUBLIC_DEMO_SKUS
        and product_list_item(db, p).get("readiness") == ProductReadiness.ready_to_publish.value
    ]


def _bootstrap(db: Session) -> None:
    from app.api.routes import import_fixture_batch, start_process, start_publish

    batch = db.scalar(select(Batch).where(Batch.name == PUBLIC_DEMO_BATCH))
    if not batch:
        batch = import_fixture_batch(
            db,
            csv_name="seiko_demo_catalog.csv",
            batch_name=PUBLIC_DEMO_BATCH,
            supplier_name="Pacific Watch Distributors",
            batch_kind=BatchKind.demo,
        )

    process_job = _run_job(db, start_process, batch.id)
    if process_job:
        execute_job(db, str(process_job.id))

    _accept_safe_decisions(db, batch.id)

    for product in db.scalars(select(Product).where(Product.batch_id == batch.id)).all():
        refresh_product_readiness(db, product)
    db.commit()

    ready_ids = ready_public_demo_ids(db, batch.id)
    if not ready_ids:
        logger.warning("Public demo catalog processed but no curated products were ready to publish")
        return

    pub_job = start_publish(batch.id, PublishRequest(product_ids=ready_ids, verify=True), db)
    execute_job(db, str(pub_job.id))
    published = db.scalar(select(func.count()).select_from(StoreProduct)) or 0
    logger.info("Published %s demonstration products to the public storefront", published)


def _run_job(db: Session, starter, batch_id: uuid.UUID) -> Job | None:
    running = db.scalar(
        select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running])).limit(1)
    )
    if running and running.batch_id == batch_id:
        return running
    if running:
        logger.warning("Another job is active; waiting is not possible during bootstrap")
        return None
    try:
        return starter(batch_id, db)
    except HTTPException as exc:
        logger.warning("Could not start bootstrap job: %s", exc.detail)
        return None


def _accept_safe_decisions(db: Session, batch_id: uuid.UUID) -> None:
    from app.api.routes import resolve_decision

    def pending_for_batch() -> list[Decision]:
        return list(
            db.scalars(
                select(Decision).where(
                    Decision.batch_id == batch_id,
                    Decision.status == DecisionStatus.pending,
                )
            ).all()
        )

    # First consume retrieved evidence, then accept supplier labels already on the row.
    for decision in pending_for_batch():
        if decision.kind in SAFE_BOOTSTRAP_KINDS:
            if decision.kind == DecisionKind.accept_enrichment and decision.proposed_value is None:
                continue
            if decision.kind == DecisionKind.no_primary_image and decision.proposed_value is None:
                continue
            _approve(db, decision)
        if (
            decision.kind == DecisionKind.conflicting_variant
            and decision.field_name != "primary_image"
            and decision.proposed_value is not None
        ):
            _approve(db, decision)

    for decision in pending_for_batch():
        if decision.kind not in {
            DecisionKind.unknown_brand_alias,
            DecisionKind.unknown_color_alias,
            DecisionKind.ambiguous_category,
        }:
            continue
        value = decision.proposed_value or decision.original_value
        if not value and decision.product_id:
            product = db.get(Product, decision.product_id)
            if product and product.current_version_id:
                version = db.get(ProductVersion, product.current_version_id)
                if version and decision.field_name:
                    value = (version.proposed or {}).get(decision.field_name)
        if not value:
            continue
        try:
            resolve_decision(
                decision.id,
                DecisionResolve(action="edit", edited_value=value),
                db,
            )
        except Exception:
            logger.exception("Could not accept supplier label for demo decision %s", decision.id)
            db.rollback()


def _approve(db: Session, decision: Decision) -> None:
    from app.api.routes import resolve_decision

    try:
        resolve_decision(decision.id, DecisionResolve(action="approve"), db)
    except Exception:
        logger.exception("Could not auto-approve demo decision %s", decision.id)
        db.rollback()
        return
    if decision.product_id and decision.field_name:
        rows = db.scalars(
            select(FieldEvidence).where(
                FieldEvidence.product_id == decision.product_id,
                FieldEvidence.field_name == decision.field_name,
            )
        ).all()
        for row in rows:
            if row.acceptance_status == EvidenceAcceptance.pending:
                row.acceptance_status = EvidenceAcceptance.accepted
        product = db.get(Product, decision.product_id)
        if product:
            refresh_product_readiness(db, product)
        db.commit()
