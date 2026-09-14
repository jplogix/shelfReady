"""Public demonstration catalog can be processed and published without operator UI."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("LOOKUP_PROVIDER", "replay")
os.environ.setdefault("FIXTURES_ROOT", str(ROOT / "fixtures"))
os.environ.setdefault("STORAGE_ROOT", str(ROOT / "storage"))

from app.agent.runner import execute_job
from app.api.routes import import_fixture_batch, start_process, start_publish
from app.api.schemas import PublishRequest
from app.config import get_settings
from app.db.models import BatchKind, Job, JobStatus, Product, StoreProduct
from app.db.session import SessionLocal
from app.main import app
from app.policy.readiness import refresh_product_readiness
from app.services.bootstrap_storefront import _accept_safe_decisions
from app.services.demo_catalog import HOUSEHOLD_DEMO_SKUS, canonical_sku

get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_catalog_publishes_ready_products_and_exposes_provenance(client):
    db = SessionLocal()
    slugs: list[str] = []
    try:
        for job in db.scalars(select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running]))).all():
            job.status = JobStatus.failed
            job.error = "cleared_for_public_demo_test"
        db.commit()

        batch = import_fixture_batch(
            db,
            csv_name="demo_catalog.csv",
            batch_name=f"Public demo test {uuid.uuid4()}",
            supplier_name="Household Essentials Co.",
            batch_kind=BatchKind.demo,
        )
        job = start_process(batch.id, db)
        execute_job(db, str(job.id))
        _accept_safe_decisions(db, batch.id)
        for product in db.scalars(select(Product).where(Product.batch_id == batch.id)).all():
            refresh_product_readiness(db, product)
        db.commit()
        ready_ids = [
            p.id
            for p in db.scalars(select(Product).where(Product.batch_id == batch.id)).all()
            if canonical_sku(p.supplier_sku or p.sku) in HOUSEHOLD_DEMO_SKUS
            and (p.readiness.value if p.readiness else None) == "ready_to_publish"
        ]
        if not ready_ids:
            from app.policy.readiness import refresh_product_readiness as refresh

            for product in db.scalars(select(Product).where(Product.batch_id == batch.id)).all():
                refresh(db, product)
            db.commit()
            ready_ids = [
                p.id
                for p in db.scalars(select(Product).where(Product.batch_id == batch.id)).all()
                if canonical_sku(p.supplier_sku or p.sku) in HOUSEHOLD_DEMO_SKUS
                and (p.readiness.value if p.readiness else None) == "ready_to_publish"
            ]
        assert ready_ids, "Household demo catalog should yield curated publishable products after safe approvals"
        pub = start_publish(batch.id, PublishRequest(product_ids=ready_ids, verify=True), db)
        result = execute_job(db, str(pub.id))
        assert result.get("published", 0) >= 1, result
        skus = [p.sku for p in db.scalars(select(Product).where(Product.id.in_(ready_ids))).all()]
        published = db.scalars(select(StoreProduct).where(StoreProduct.variant_sku.in_(skus))).all()
        assert published, result
        titles = [row.title for row in published]
        assert all("CONFLICT" not in title for title in titles)
        assert all("Invalid Barcode" not in title for title in titles)
        for row in published:
            path = row.primary_image_path or ""
            assert "hoodie" not in path
            assert "aurora-mug" not in path
        published_rows = [
            {"title": row.title, "slug": row.slug} for row in published
        ]
        assert all(sku.split("__")[0] in HOUSEHOLD_DEMO_SKUS for sku in skus)
    finally:
        db.close()

    coke = next((row for row in published_rows if "Coca-Cola" in row["title"]), None)
    assert coke is not None, "Sparse barcode row should publish as an enriched Coca-Cola listing"
    provenance = client.get(f"/api/store/products/{coke['slug']}/provenance")
    assert provenance.status_code == 200, provenance.text
    body = provenance.json()
    assert body["original_row"] is not None
    assert isinstance(body["corrections"], list)
    assert isinstance(body["evidence"], list)
    assert body["original_fields"]
    assert "label" in body["original_fields"][0]
    if body["corrections"]:
        assert "label" in body["corrections"][0]
    assert body["agent_mode"] in {"replay", "live"}
    if "Coca-Cola" in coke["title"]:
        assert body["evidence"] or body["corrections"]
