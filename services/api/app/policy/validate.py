"""Publication eligibility and approval enforcement (backend, not prompt-only)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.policy.money import MoneyError, is_suspicious_price, parse_money, parse_stock


def compute_diffs(original: dict[str, Any], proposed: dict[str, Any]) -> list[dict[str, Any]]:
    keys = sorted(set(original) | set(proposed))
    diffs: list[dict[str, Any]] = []
    for key in keys:
        ov = original.get(key)
        pv = proposed.get(key)
        if ov != pv:
            diffs.append({"field": key, "original": ov, "proposed": pv})
    return diffs


def validate_product_fields(
    proposed: dict[str, Any],
    *,
    currency: str = "USD",
    median_price: Decimal | None = None,
    require_primary_image: bool = True,
    has_primary_image: bool = False,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    price = proposed.get("price")
    try:
        amount, cur = parse_money(price, currency)
        proposed["price"] = str(amount)
        proposed["currency"] = cur
        if is_suspicious_price(amount, median=median_price):
            reviews.append(
                {
                    "kind": "suspicious_price",
                    "field": "price",
                    "reason": "Price flagged by documented anomaly heuristics (not proof of error).",
                    "value": str(amount),
                }
            )
    except MoneyError as exc:
        code = str(exc)
        blockers.append(
            {
                "kind": "missing_price" if "missing" in code else "invalid_price",
                "field": "price",
                "reason": f"Price validation failed: {code}",
                "value": price,
            }
        )

    try:
        stock = parse_stock(proposed.get("stock"))
        proposed["stock"] = stock
        proposed["available"] = stock > 0
    except ValueError as exc:
        code = str(exc)
        blockers.append(
            {
                "kind": "invalid_stock",
                "field": "stock",
                "reason": f"Stock validation failed: {code}",
                "value": proposed.get("stock"),
            }
        )

    for required in ("sku", "title", "brand"):
        if not proposed.get(required):
            blockers.append(
                {
                    "kind": "missing_field",
                    "field": required,
                    "reason": f"Required field '{required}' is missing.",
                    "value": proposed.get(required),
                }
            )

    if require_primary_image and not has_primary_image:
        blockers.append(
            {
                "kind": "no_primary_image",
                "field": "primary_image",
                "reason": "No suitable primary product image.",
                "value": None,
            }
        )

    publishable = len(blockers) == 0 and not any(
        r["kind"] in {"suspicious_price"} for r in reviews
    )
    # Suspicious price still blocks auto-publish until reviewed
    if any(r["kind"] == "suspicious_price" for r in reviews):
        publishable = False

    return {
        "proposed": proposed,
        "blockers": blockers,
        "reviews": reviews,
        "is_publishable": publishable,
    }


def approval_is_valid(
    *,
    approved_version_id: str | None,
    current_version_id: str | None,
    publication_decision_approved: bool = False,
    auto_publish_demo: bool = False,
) -> bool:
    if approved_version_id is None or current_version_id is None:
        return False
    if str(approved_version_id) != str(current_version_id):
        return False  # stale approval
    if auto_publish_demo or publication_decision_approved:
        return True
    # Batch publish sets approved_version_id explicitly before calling publish_product
    return True


def price_or_inventory_changed(diffs: list[dict[str, Any]]) -> bool:
    return any(d["field"] in {"price", "stock", "currency"} for d in diffs)
