"""Decision resolution policy tests."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")

from app.config import get_settings
from app.db.models import Decision, DecisionKind, DecisionStatus
from app.db.session import SessionLocal
from app.main import app

get_settings.cache_clear()
AUTH = {"Authorization": "Bearer dev-token-change-me"}


@pytest.fixture
def client():
    return TestClient(app)


def test_approve_null_missing_price_rejected(client):
    r = client.post("/api/demo/load-sample", headers=AUTH)
    assert r.status_code == 200
    batch_id = r.json()["id"]
    from app.agent.runner import execute_job
    from app.db.models import Job, JobStatus
    from sqlalchemy import select

    db = SessionLocal()
    try:
        from app.db.models import Job, JobStatus
        from sqlalchemy import select

        for j in db.scalars(
            select(Job).where(Job.status.in_([JobStatus.pending, JobStatus.running]))
        ).all():
            j.status = JobStatus.failed
            j.error = "cleared_for_test"
        db.commit()
    finally:
        db.close()

    pr = client.post(f"/api/batches/{batch_id}/process", headers=AUTH)
    assert pr.status_code == 200, pr.text
    job_id = pr.json()["id"]
    db = SessionLocal()
    try:
        execute_job(db, job_id)
        missing = db.scalars(
            select(Decision).where(
                Decision.batch_id == uuid.UUID(batch_id),
                Decision.kind == DecisionKind.missing_price,
                Decision.status == DecisionStatus.pending,
            )
        ).first()
        assert missing
        dr = client.post(
            f"/api/decisions/{missing.id}/resolve",
            headers=AUTH,
            json={"action": "approve"},
        )
        assert dr.status_code == 400
    finally:
        db.close()
