"""
validators.py
-------------
Pure-function validators for CLI input.
Raises ValueError with a clear message on any bad input.
"""

from __future__ import annotations

VALID_SIDES       = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


def validate_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.isalnum():
        raise ValueError(f"Invalid symbol '{symbol}'. Use alphanumeric only, e.g. BTCUSDT.")
    return s


def validate_side(side: str) -> str:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(f"Invalid side '{side}'. Must be one of: {', '.join(VALID_SIDES)}.")
    return s


def validate_order_type(order_type: str) -> str:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(VALID_ORDER_TYPES)}."
        )
    return t


def validate_quantity(quantity: str | float) -> float:
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if q <= 0:
        raise ValueError(f"Quantity must be greater than 0, got {q}.")
    return q


def validate_price(price: str | float | None, order_type: str) -> float | None:
    if order_type.upper() == "LIMIT":
        if price is None:
            raise ValueError("Price is required for LIMIT orders.")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid price '{price}'. Must be a positive number.")
        if p <= 0:
            raise ValueError(f"Price must be greater than 0, got {p}.")
        return p

    if order_type.upper() == "STOP_MARKET":
        if price is None:
            raise ValueError("Stop price is required for STOP_MARKET orders (pass via --price).")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid stop price '{price}'.")
        if p <= 0:
            raise ValueError(f"Stop price must be greater than 0, got {p}.")
        return p

    return None   # MARKET – price not needed
