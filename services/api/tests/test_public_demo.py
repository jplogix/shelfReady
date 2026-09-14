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
from app.db.models import BatchKind, Job, JobStatus, Product, ProductReadiness
from app.db.session import SessionLocal
from app.main import app
from app.policy.readiness import refresh_product_readiness
from app.services.batch_metrics import product_list_item
from app.services.bootstrap_storefront import _accept_safe_decisions

get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_catalog_publishes_ready_products_and_exposes_provenance(client):
    db = SessionLocal()
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
            if product_list_item(db, p).get("readiness") == ProductReadiness.ready_to_publish.value
        ]
        assert ready_ids, "Demo catalog should yield at least one publishable product after safe approvals"
        pub = start_publish(batch.id, PublishRequest(product_ids=ready_ids, verify=True), db)
        execute_job(db, str(pub.id))
    finally:
        db.close()

    listed = client.get("/api/store/products")
    assert listed.status_code == 200
    products = listed.json()
    assert len(products) >= 1
    sample = products[0]
    assert "external_id" not in sample
    assert sample["title"]
    provenance = client.get(f"/api/store/products/{sample['slug']}/provenance")
    assert provenance.status_code == 200, provenance.text
    body = provenance.json()
    assert body["original_row"] is not None
    assert isinstance(body["corrections"], list)
    assert isinstance(body["evidence"], list)
    assert body["agent_mode"] in {"replay", "live"}
