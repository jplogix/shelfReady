"""Auth boundary and production configuration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("SHELFREADY_API_TOKEN", "dev-token-change-me")
os.environ.setdefault("AGENT_MODE", "replay")
os.environ.setdefault("ENVIRONMENT", "development")

from app.config import Settings, get_settings
from app.main import app

get_settings.cache_clear()
AUTH = {"Authorization": "Bearer dev-token-change-me"}


@pytest.fixture
def client():
    return TestClient(app)


def test_storefront_list_is_public(client):
    r = client.get("/api/store/products")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    if r.json():
        item = r.json()[0]
        assert "slug" in item
        assert "title" in item
        assert "external_id" not in item
        assert "json_ld" not in item
        assert "seo" not in item


def test_listing_provenance_is_public_and_404_for_unknown(client):
    r = client.get("/api/store/products/not-a-real-slug/provenance")
    assert r.status_code == 404


def test_operator_write_requires_token(client):
    r = client.post("/api/demo/load-demo")
    assert r.status_code == 401


def test_mode_is_public_and_separates_lookup(client):
    r = client.get("/api/mode")
    assert r.status_code == 200
    body = r.json()
    assert "lookup_mode" in body
    assert "agent_mode" in body
    assert body["lookup_is_replay"] is True


def test_production_rejects_localhost_database():
    with pytest.raises(ValidationError, match="localhost"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready",
            shelfready_api_token="not-a-default-token",
        )


def test_production_rejects_default_api_token():
    with pytest.raises(ValidationError, match="SHELFREADY_API_TOKEN"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://shelfready:secret@db.example:5432/shelfready",
            shelfready_api_token="dev-token-change-me",
        )
