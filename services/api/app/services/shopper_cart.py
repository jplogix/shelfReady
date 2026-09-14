"""Shopper cart helpers. Isolated from verification carts; prices come from the store row."""

from __future__ import annotations

import uuid

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CartItemOut, CartOut
from app.db.models import Cart, CartItem, StoreProduct, Workspace

SHOPPER_COOKIE = "sr_shopper_cart"
SHOPPER_PURPOSE = "shopper"
VERIFICATION_PURPOSE = "verification"
OPERATOR_PURPOSE = "operator"


def parse_cart_id(raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def get_or_create_cart(
    db: Session,
    workspace: Workspace,
    *,
    purpose: str,
    cart_id: uuid.UUID | None = None,
) -> Cart:
    if purpose == VERIFICATION_PURPOSE:
        cart = Cart(id=uuid.uuid4(), workspace_id=workspace.id, purpose=VERIFICATION_PURPOSE)
        db.add(cart)
        db.flush()
        return cart
    if purpose == SHOPPER_PURPOSE:
        if cart_id:
            existing = db.get(Cart, cart_id)
            if existing and existing.workspace_id == workspace.id and existing.purpose == SHOPPER_PURPOSE:
                return existing
        cart = Cart(id=uuid.uuid4(), workspace_id=workspace.id, purpose=SHOPPER_PURPOSE)
        db.add(cart)
        db.flush()
        return cart
    cart = db.scalar(
        select(Cart).where(Cart.workspace_id == workspace.id, Cart.purpose == purpose).limit(1)
    )
    if cart:
        return cart
    cart = Cart(id=uuid.uuid4(), workspace_id=workspace.id, purpose=purpose)
    db.add(cart)
    db.flush()
    return cart


def add_store_item(db: Session, cart: Cart, store_product: StoreProduct, quantity: int) -> Cart:
    if quantity < 1:
        raise HTTPException(400, "Quantity must be at least 1")
    if not store_product.available or store_product.stock <= 0:
        raise HTTPException(400, "Out of stock — cannot add to cart")
    existing = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.store_product_id == store_product.id
        )
    )
    new_qty = (existing.quantity if existing else 0) + quantity
    if new_qty > store_product.stock:
        raise HTTPException(400, "Requested quantity exceeds available stock")
    if existing:
        existing.quantity = new_qty
        existing.unit_price = store_product.price
        existing.currency = store_product.currency
    else:
        db.add(
            CartItem(
                id=uuid.uuid4(),
                cart_id=cart.id,
                store_product_id=store_product.id,
                quantity=quantity,
                unit_price=store_product.price,
                currency=store_product.currency,
            )
        )
    db.flush()
    return cart


def set_item_quantity(db: Session, cart: Cart, store_product_id: uuid.UUID, quantity: int) -> Cart:
    item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.store_product_id == store_product_id)
    )
    if not item:
        raise HTTPException(404, "Cart item not found")
    if quantity < 1:
        db.delete(item)
        db.flush()
        return cart
    sp = db.get(StoreProduct, store_product_id)
    if not sp:
        raise HTTPException(404, "Product not found")
    if quantity > sp.stock:
        raise HTTPException(400, "Requested quantity exceeds available stock")
    item.quantity = quantity
    item.unit_price = sp.price
    item.currency = sp.currency
    db.flush()
    return cart


def remove_item(db: Session, cart: Cart, store_product_id: uuid.UUID) -> Cart:
    item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.store_product_id == store_product_id)
    )
    if item:
        db.delete(item)
        db.flush()
    return cart


def cart_out(db: Session, cart: Cart) -> CartOut:
    items = []
    subtotal = Decimal("0")
    currency = "USD"
    count = 0
    for it in cart.items:
        sp = db.get(StoreProduct, it.store_product_id)
        line = (it.unit_price or Decimal("0")) * it.quantity
        subtotal += line
        currency = it.currency or currency
        count += it.quantity
        items.append(
            CartItemOut(
                id=it.id,
                store_product_id=it.store_product_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                currency=it.currency,
                title=sp.title if sp else None,
                slug=sp.slug if sp else None,
                image=sp.primary_image_path if sp else None,
                available=bool(sp.available) if sp else False,
                stock=sp.stock if sp else 0,
                line_total=line,
            )
        )
    return CartOut(
        id=cart.id,
        purpose=cart.purpose,
        items=items,
        subtotal=subtotal,
        currency=currency,
        item_count=count,
    )
