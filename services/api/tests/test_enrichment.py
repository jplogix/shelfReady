"""Enrichment and evidence tests (replay mode)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("LOOKUP_PROVIDER", "replay")
os.environ.setdefault("FIXTURES_ROOT", str(ROOT / "fixtures"))

from app.db.models import Decision, DecisionKind, FieldEvidence, MatchOutcome, Product
from app.db.session import SessionLocal
from app.enrichment.service import EnrichmentBudget, enrich_product, get_provider
from app.services.catalog import process_product


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_enrichment_conflict_not_silent(db):
    from app.db.models import Batch, BatchKind, Workspace, ProductStatus

    ws = db.scalar(select(Workspace).limit(1))
    batch = Batch(id=uuid.uuid4(), workspace_id=ws.id, name="t", supplier_name="s", batch_kind=BatchKind.demo)
    db.add(batch)
    db.flush()
    product = Product(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        batch_id=batch.id,
        sku="HC-COKE-02",
        supplier_sku="HC-COKE-02",
        status=ProductStatus.imported,
    )
    db.add(product)
    db.flush()
    original = {
        "sku": "HC-COKE-02",
        "title": "Coca-Cola",
        "brand": "Coca-Cola",
        "color": "Black",
        "upc": "049000028911",
        "price": "1.99",
        "currency": "USD",
        "stock": "10",
    }
    version = process_product(db, product, original)
    provider = get_provider(ROOT / "fixtures")
    budget = EnrichmentBudget(10)
    enrich_product(db, product, version, original, provider, budget)
    db.flush()
    conflict = db.scalars(
        select(Decision).where(
            Decision.product_id == product.id,
            Decision.kind == DecisionKind.conflicting_variant,
        )
    ).first()
    assert conflict is not None
    evidence = db.scalars(select(FieldEvidence).where(FieldEvidence.product_id == product.id)).all()
    assert any(e.match_outcome == MatchOutcome.conflicting_evidence for e in evidence)


def test_lookup_unavailable_does_not_block_publishable(db):
    from app.db.models import Batch, Workspace, ProductStatus

    ws = db.scalar(select(Workspace).limit(1))
    batch = Batch(id=uuid.uuid4(), workspace_id=ws.id, name="t2", supplier_name="s")
    db.add(batch)
    db.flush()
    product = Product(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        batch_id=batch.id,
        sku="NO-BAR",
        status=ProductStatus.imported,
    )
    db.add(product)
    db.flush()
    original = {
        "sku": "NO-BAR",
        "title": "Complete Product",
        "brand": "Acme",
        "price": "9.99",
        "currency": "USD",
        "stock": "5",
        "image_filename": "",
    }
    version = process_product(db, product, original)
    assert version.is_publishable or product.status.value in {"ready", "needs_review"}
