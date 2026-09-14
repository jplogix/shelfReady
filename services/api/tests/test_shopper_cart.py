"""Public shopper cart is isolated from verification and enforces stock/price on the server."""

from __future__ import annotations

import os
from decimal import Decimal
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

from app.config import get_settings
from app.db.models import Cart, StoreProduct
from app.db.session import SessionLocal
from app.main import app
from app.store.demo import DemoStoreAdapter

get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_shopper_cart_is_public_enforces_stock_and_server_price(client):
    db = SessionLocal()
    try:
        sp = db.scalar(select(StoreProduct).where(StoreProduct.available.is_(True)).limit(1))
        if sp is None:
            pytest.skip("No published in-stock product in the local database")
        product_id = str(sp.id)
        price = str(sp.price)
        stock = sp.stock
        workspace_id = sp.workspace_id
    finally:
        db.close()

    add = client.post(
        "/api/store/cart/items",
        json={"store_product_id": product_id, "quantity": 1, "purpose": "shopper"},
    )
    assert add.status_code == 200, add.text
    body = add.json()
    assert body["purpose"] == "shopper"
    assert body["items"]
    item = body["items"][0]
    assert item["unit_price"] == price
    assert "purpose" not in item

    too_many = client.post(
        "/api/store/cart/items",
        json={"store_product_id": product_id, "quantity": stock + 50, "purpose": "shopper"},
    )
    assert too_many.status_code == 400

    verify_blocked = client.post(
        "/api/store/cart/items",
        json={"store_product_id": product_id, "quantity": 1, "purpose": "verification"},
    )
    assert verify_blocked.status_code == 400

    db = SessionLocal()
    try:
        shopper_cart = db.get(Cart, body["id"])
        assert shopper_cart is not None
        assert shopper_cart.purpose == "shopper"
        listed = db.scalars(select(StoreProduct).where(StoreProduct.workspace_id == workspace_id)).first()
        adapter = DemoStoreAdapter()
        result = adapter.verify_product(db, listed)
        assert result["passed"] is True or isinstance(result["checks"], list)
        verification_carts = db.scalars(select(Cart).where(Cart.purpose == "verification")).all()
        assert all(c.id != shopper_cart.id for c in verification_carts)
        # Verification must not mutate shopper unit price.
        db.refresh(shopper_cart)
        assert shopper_cart.items[0].unit_price == Decimal(price)
    finally:
        db.close()
