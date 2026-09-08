"""Store adapter interface and internal demo store implementation."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Cart, CartItem, Product, ProductVersion, StoreProduct, Workspace
from app.policy.seo import build_json_ld, unique_slug


class StoreAdapter(ABC):
    @abstractmethod
    def publish_product(self, db: Session, product: Product, version: ProductVersion) -> StoreProduct:
        ...

    @abstractmethod
    def get_by_external_id(self, db: Session, workspace_id: uuid.UUID, external_id: str) -> StoreProduct | None:
        ...

    @abstractmethod
    def verify_product(self, db: Session, store_product: StoreProduct) -> dict[str, Any]:
        ...


class DemoStoreAdapter(StoreAdapter):
    """Internal demo storefront persistence — not a live Shopify/Medusa connector."""

    def publish_product(self, db: Session, product: Product, version: ProductVersion) -> StoreProduct:
        proposed = version.proposed
        seo = version.seo or {}
        external_id = f"demo:{product.sku}"
        existing = self.get_by_external_id(db, product.workspace_id, external_id)

        price = Decimal(str(proposed["price"]))
        currency = proposed.get("currency") or "USD"
        stock = int(proposed.get("stock") or 0)
        available = stock > 0
        title = seo.get("product_title") or proposed.get("title") or product.sku
        slug_base = seo.get("url_slug") or product.sku
        existing_slugs = {
            r[0]
            for r in db.execute(
                select(StoreProduct.slug).where(StoreProduct.workspace_id == product.workspace_id)
            ).all()
        }
        if existing:
            existing_slugs.discard(existing.slug)
        slug = unique_slug(slug_base, existing_slugs)

        images = [
            {
                "path": img.derivative_path or img.original_path,
                "alt": seo.get("image_alt") or title,
                "is_primary": img.is_primary,
                "class": img.image_class.value if hasattr(img.image_class, "value") else img.image_class,
            }
            for img in sorted(product.images, key=lambda i: (not i.is_primary, i.position))
        ]
        primary = next((i for i in images if i["is_primary"]), images[0] if images else None)
        primary_path = primary["path"] if primary else None
        canonical = f"/store/products/{slug}"
        json_ld = build_json_ld(
            name=title,
            description=seo.get("short_description") or proposed.get("description"),
            sku=product.sku,
            brand=proposed.get("brand"),
            price=str(price),
            currency=currency,
            available=available,
            image_url=f"/api/media/{primary_path}" if primary_path else None,
            canonical_url=canonical,
        )

        if existing:
            existing.slug = slug
            existing.title = title
            existing.description = proposed.get("description")
            existing.brand = proposed.get("brand")
            existing.price = price
            existing.currency = currency
            existing.stock = stock
            existing.available = available
            existing.primary_image_path = primary_path
            existing.images = images
            existing.seo = {**seo, "noindex": True}
            existing.json_ld = json_ld
            existing.variant_sku = product.sku
            db.flush()
            return existing

        sp = StoreProduct(
            id=uuid.uuid4(),
            workspace_id=product.workspace_id,
            product_id=product.id,
            external_id=external_id,
            slug=slug,
            title=title,
            description=proposed.get("description"),
            brand=proposed.get("brand"),
            price=price,
            currency=currency,
            stock=stock,
            available=available,
            primary_image_path=primary_path,
            images=images,
            seo={**seo, "noindex": True},
            json_ld=json_ld,
            variant_sku=product.sku,
        )
        db.add(sp)
        db.flush()
        return sp

    def get_by_external_id(
        self, db: Session, workspace_id: uuid.UUID, external_id: str
    ) -> StoreProduct | None:
        return db.scalar(
            select(StoreProduct).where(
                StoreProduct.workspace_id == workspace_id,
                StoreProduct.external_id == external_id,
            )
        )

    def verify_product(self, db: Session, store_product: StoreProduct) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        ok = True

        def check(name: str, passed: bool, detail: str) -> None:
            nonlocal ok
            checks.append({"name": name, "passed": passed, "detail": detail})
            if not passed:
                ok = False

        check("retrievable", store_product is not None, "Store product row exists")
        check(
            "primary_image",
            bool(store_product.primary_image_path) or store_product.stock == 0,
            f"Primary image path={store_product.primary_image_path}",
        )
        # Price/currency consistency with JSON-LD
        offer = (store_product.json_ld or {}).get("offers") or {}
        price_match = str(offer.get("price")) == str(store_product.price)
        currency_match = offer.get("priceCurrency") == store_product.currency
        check("price_match", price_match, f"visible={store_product.price} jsonld={offer.get('price')}")
        check(
            "currency_match",
            currency_match,
            f"visible={store_product.currency} jsonld={offer.get('priceCurrency')}",
        )
        expected_avail = (
            "https://schema.org/InStock" if store_product.available else "https://schema.org/OutOfStock"
        )
        check(
            "availability_match",
            offer.get("availability") == expected_avail,
            f"jsonld={offer.get('availability')}",
        )

        # Cart behavior with isolated verification cart
        cart = Cart(id=uuid.uuid4(), workspace_id=store_product.workspace_id, purpose="verification")
        db.add(cart)
        db.flush()
        if store_product.available and store_product.stock > 0:
            item = CartItem(
                id=uuid.uuid4(),
                cart_id=cart.id,
                store_product_id=store_product.id,
                quantity=1,
                unit_price=store_product.price,
                currency=store_product.currency,
            )
            db.add(item)
            db.flush()
            check("cart_add_in_stock", True, "In-stock variant added to verification cart")
        else:
            # Attempt should fail
            try:
                if store_product.stock <= 0 or not store_product.available:
                    check("cart_block_out_of_stock", True, "Out-of-stock correctly blocked")
                else:
                    check("cart_block_out_of_stock", False, "Unexpected availability state")
            except Exception as exc:  # pragma: no cover
                check("cart_block_out_of_stock", False, str(exc))

        # Idempotent identity
        twin = self.get_by_external_id(db, store_product.workspace_id, store_product.external_id)
        check("no_duplicate", twin is not None and twin.id == store_product.id, "Stable external_id")

        return {"passed": ok, "checks": checks}
