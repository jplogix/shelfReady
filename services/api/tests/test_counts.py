"""Batch count reconciliation tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("LOOKUP_PROVIDER", "replay")
os.environ.setdefault("FIXTURES_ROOT", str(ROOT / "fixtures"))

from app.config import get_settings
from app.main import app

get_settings.cache_clear()
AUTH = {"Authorization": "Bearer dev-token-change-me"}


@pytest.fixture
def client():
    return TestClient(app)


def test_batch_counts_reconcile(client):
    r = client.post("/api/demo/load-demo", headers=AUTH)
    assert r.status_code == 200
    batch_id = r.json()["id"]
    r = client.get(f"/api/batches/{batch_id}", headers=AUTH)
    counts = r.json()["counts"]
    assert counts["products"] >= 8
    total_unpublished = (
        counts.get("ready_to_publish", 0)
        + counts.get("needs_information", 0)
        + counts.get("has_conflicts", 0)
    )
    assert counts["products"] >= total_unpublished + counts.get("published", 0) - counts.get("verification_failed", 0)
