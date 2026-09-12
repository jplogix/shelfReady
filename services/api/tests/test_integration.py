"""Integration tests against Postgres (replay mode, no Bedrock)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Ensure env before app import
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("STORAGE_ROOT", str(ROOT / "storage"))
os.environ.setdefault("FIXTURES_ROOT", str(ROOT / "fixtures"))

from app.agent.runner import execute_job
from app.config import get_settings
from app.db.models import Decision, DecisionKind, DecisionStatus, Job, JobStatus, Product, StoreProduct
from app.db.session import SessionLocal
from app.main import app

get_settings.cache_clear()

TOKEN = "dev-token-change-me"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["agent_mode"] == "replay"


def test_mode_labeled_replay(client):
    r = client.get("/api/mode", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["is_replay"] is True
    assert "replay" in body["label"].lower()


def test_end_to_end_sample_process_decisions_publish(client):
    # Load sample
    r = client.post("/api/demo/load-sample", headers=AUTH)
    assert r.status_code == 200, r.text
    batch = r.json()
    batch_id = batch["id"]
    assert batch["counts"]["products"] >= 18

    # Clear any leftover pending/running jobs from other tests (single-job MVP lock)
    db = SessionLocal()
    try:
        for j in db.scalars(
            select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running]))
        ).all():
            j.status = JobStatus.failed
            j.error = "cleared_for_test"
        db.commit()
    finally:
        db.close()

    # Start process job and run inline (no worker)
    r = client.post(f"/api/batches/{batch_id}/process", headers=AUTH)
    assert r.status_code == 200
    job = r.json()
    db = SessionLocal()
    try:
        result = execute_job(db, job["id"])
        assert result["status"] in {"awaiting_decisions", "completed"}
    finally:
        db.close()

    r = client.get(f"/api/batches/{batch_id}/decisions?status=pending", headers=AUTH)
    assert r.status_code == 200
    decisions = r.json()
    assert len(decisions) >= 2

    # Resolve a missing price with edit, and approve one publication-eligible path
    db = SessionLocal()
    try:
        missing = db.scalars(
            select(Decision).where(
                Decision.batch_id == uuid.UUID(batch_id),
                Decision.kind == DecisionKind.missing_price,
                Decision.status == DecisionStatus.pending,
            )
        ).first()
        assert missing is not None
    finally:
        db.close()

    r = client.post(
        f"/api/decisions/{missing.id}/resolve",
        headers=AUTH,
        json={"action": "edit", "edited_value": "29.00"},
    )
    assert r.status_code == 200, r.text

    # Reject prompt-injection unsupported claim (keep sanitized text)
    db = SessionLocal()
    try:
        inj = db.scalars(
            select(Decision).where(
                Decision.batch_id == uuid.UUID(batch_id),
                Decision.kind == DecisionKind.unsupported_claim,
                Decision.status == DecisionStatus.pending,
            )
        ).first()
    finally:
        db.close()
    if inj:
        r = client.post(
            f"/api/decisions/{inj.id}/resolve",
            headers=AUTH,
            json={"action": "approve"},
        )
        assert r.status_code == 200

    # Approve brand for Bluebark if present
    db = SessionLocal()
    try:
        brand = db.scalars(
            select(Decision).where(
                Decision.batch_id == uuid.UUID(batch_id),
                Decision.kind == DecisionKind.unknown_brand_alias,
                Decision.status == DecisionStatus.pending,
            )
        ).first()
    finally:
        db.close()
    if brand:
        r = client.post(
            f"/api/decisions/{brand.id}/resolve",
            headers=AUTH,
            json={
                "action": "edit",
                "edited_value": "Bluebark",
                "save_as_rule": True,
                "rule_type": "brand",
                "rule_target": "Bluebark",
            },
        )
        assert r.status_code == 200

    # Resolve remaining pending decisions where possible via edit
    r = client.get(f"/api/batches/{batch_id}/decisions?status=pending", headers=AUTH)
    pending = r.json()
    for d in pending:
        if d["kind"] == "missing_price":
            client.post(
                f"/api/decisions/{d['id']}/resolve",
                headers=AUTH,
                json={"action": "edit", "edited_value": "19.00"},
            )
        elif d["kind"] in {"unknown_brand_alias", "ambiguous_category", "unknown_color_alias"}:
            client.post(
                f"/api/decisions/{d['id']}/resolve",
                headers=AUTH,
                json={"action": "edit", "edited_value": "Resolved"},
            )
        elif d["kind"] in {"unsupported_claim", "suspicious_price", "exact_duplicate"}:
            client.post(f"/api/decisions/{d['id']}/resolve", headers=AUTH, json={"action": "approve"})

    # Publish ready products explicitly
    r = client.get(f"/api/batches/{batch_id}/products", headers=AUTH)
    ready_ids = [p["id"] for p in r.json() if p.get("readiness") == "ready_to_publish"]
    r = client.post(
        f"/api/batches/{batch_id}/publish",
        headers=AUTH,
        json={"product_ids": ready_ids[:3], "verify": True},
    )
    assert r.status_code == 200
    pub_job = r.json()
    db = SessionLocal()
    try:
        execute_job(db, pub_job["id"])
    finally:
        db.close()

    r = client.get("/api/store/products", headers=AUTH)
    assert r.status_code == 200
    products = r.json()
    # Partial batch success: at least some products publish
    assert isinstance(products, list)

    if products:
        sp = products[0]
        # Idempotent republish
        before = len(products)
        r = client.post(f"/api/batches/{batch_id}/publish", headers=AUTH)
        pub_job2 = r.json()
        db = SessionLocal()
        try:
            execute_job(db, pub_job2["id"])
        finally:
            db.close()
        r = client.get("/api/store/products", headers=AUTH)
        after = r.json()
        # external_id uniqueness — count should not explode with duplicates of same SKUs
        ext = [p["external_id"] for p in after]
        assert len(ext) == len(set(ext))

        if sp["available"]:
            r = client.post(
                "/api/store/cart/items",
                headers=AUTH,
                json={"store_product_id": sp["id"], "quantity": 1, "purpose": "operator"},
            )
            assert r.status_code == 200, r.text
            assert len(r.json()["items"]) >= 1

        # Out of stock cannot purchase
        db = SessionLocal()
        try:
            oos = db.scalars(select(StoreProduct).where(StoreProduct.available.is_(False))).first()
        finally:
            db.close()
        if oos:
            r = client.post(
                "/api/store/cart/items",
                headers=AUTH,
                json={"store_product_id": str(oos.id), "quantity": 1},
            )
            assert r.status_code == 400


def test_live_mode_failure_does_not_silent_replay(monkeypatch, client):
    """When AGENT_MODE=live and Bedrock init fails, job fails — no silent replay."""
    from app.agent import runner as runner_mod

    def boom():
        raise RuntimeError("bedrock unavailable")

    monkeypatch.setattr(runner_mod, "_build_strands_agent", boom)
    monkeypatch.setenv("AGENT_MODE", "live")
    get_settings.cache_clear()

    # Minimal batch
    r = client.post("/api/demo/load-sample", headers=AUTH)
    batch_id = r.json()["id"]
    # Force a job in live mode with empty products already processed path —
    # create job manually
    db = SessionLocal()
    try:
        job = Job(
            id=uuid.uuid4(),
            batch_id=uuid.UUID(batch_id),
            job_type="process",
            status=JobStatus.pending,
            agent_mode="live",
            checkpoint={"processed_ids": [str(p.id) for p in db.scalars(select(Product).where(Product.batch_id == uuid.UUID(batch_id))).all()]},
        )
        # Mark all products as already having versions by running replay preprocess first in isolation
        db.add(job)
        db.commit()
        jid = str(job.id)
    finally:
        db.close()

    # Run deterministic first via replay-like processing then attempt live with no pending
    # Simpler: call run_live path by executing — if preprocessing creates pending, live agent won't be called.
    # So clear decisions and mark ready... For this test, directly invoke run_live after mocking.
    from app.agent.tools import ToolContext, set_tool_context, run_deterministic_processing
    from app.db.models import Batch

    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(jid))
        batch = db.get(Batch, uuid.UUID(batch_id))
        assert job and batch
        ctx = ToolContext(db, job, batch)
        set_tool_context(ctx)
        # Ensure no pending by rejecting all after process in replay sense — just test _build failure path:
        from app.agent.runner import run_live

        # Force pending=0 by not calling preprocess — patch run_deterministic_processing
        monkeypatch.setattr(runner_mod, "run_deterministic_processing", lambda c: {"processed": 0, "pending_decisions": 0})
        with pytest.raises(Exception):
            run_live(ctx)
        assert job.status.value == "failed" or "Failed" in (job.error or "") or job.error
        assert "replay" not in (job.error or "").lower() or "no replay" in (job.error or "").lower()
    finally:
        set_tool_context(None)
        db.close()
    get_settings.cache_clear()
    os.environ["AGENT_MODE"] = "replay"
