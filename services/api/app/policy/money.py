"""Decimal-safe money and stock validation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class MoneyError(ValueError):
    pass


def parse_money(value: Any, currency: str = "USD") -> tuple[Decimal, str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise MoneyError("missing_price")
    raw = str(value).strip().replace(",", "").replace("$", "")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f"invalid_price:{value}") from exc
    if amount < 0:
        raise MoneyError("negative_price")
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return quantized, currency.upper()


def is_suspicious_price(amount: Decimal, *, median: Decimal | None = None) -> bool:
    """Heuristic anomalies — labeled as anomalies, not proof of error.

    - Price below $1.00 for catalog goods (possible missing decimals)
    - Price above $10,000
    - Price more than 5x or less than 0.2x batch median when available
    """
    if amount < Decimal("1.00"):
        return True
    if amount > Decimal("10000"):
        return True
    if median is not None and median > 0:
        if amount > median * Decimal("5") or amount < median * Decimal("0.2"):
            return True
    return False


def parse_stock(value: Any) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("missing_stock")
    try:
        stock = int(Decimal(str(value).strip()))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_stock:{value}") from exc
    if stock < 0:
        raise ValueError("negative_stock")
    return stock


def stock_available(stock: int) -> bool:
    return stock > 0
