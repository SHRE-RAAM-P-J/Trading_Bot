"""
validators.py
-------------
Pure-function validators for CLI input.
Raises ValueError with a clear message on any bad input.
"""

from __future__ import annotations

VALID_SIDES       = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TWAP"}

# Common valid futures symbols shown as hint when user types a wrong one
COMMON_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


def validate_symbol(symbol: str) -> str:
    """Basic format check — alphanumeric, non-empty, looks like a trading pair."""
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol cannot be empty. Example: BTCUSDT")
    if not s.isalnum():
        raise ValueError(f"Invalid symbol '{symbol}'. Use letters/numbers only, e.g. BTCUSDT.")
    if len(s) < 5:
        raise ValueError(
            f"Symbol '{s}' is too short. Futures symbols look like BTCUSDT, ETHUSDT.\n"
            f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
        )
    if not (s.endswith("USDT") or s.endswith("USDC") or s.endswith("BUSD") or s.endswith("BTC")):
        raise ValueError(
            f"Symbol '{s}' doesn't look like a futures pair.\n"
            f"  Futures symbols end in USDT, USDC, or BTC — e.g. BTCUSDT, ETHUSDT.\n"
            f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
        )
    return s


def validate_symbol_live(symbol: str, client) -> str:
    """
    Check symbol actually exists on the exchange.
    Requires a BinanceFuturesClient instance.
    Falls back gracefully if the API call fails.
    """
    s = validate_symbol(symbol)   # format check first
    try:
        data   = client._get("/fapi/v1/exchangeInfo")
        valid  = {item["symbol"] for item in data.get("symbols", [])}
        if s not in valid:
            # Find close matches to suggest
            suggestions = [v for v in valid if v.startswith(s[:3])][:5]
            hint = f"  Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            raise ValueError(
                f"Symbol '{s}' not found on Binance Futures.\n{hint}\n"
                f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
            )
    except ValueError:
        raise   # re-raise our own errors
    except Exception:
        pass    # if API call fails, skip live check silently
    return s


def validate_side(side: str) -> str:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}.")
    return s


def validate_order_type(order_type: str) -> str:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
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
    ot = order_type.upper()
    if ot == "LIMIT":
        if price is None:
            raise ValueError("Price is required for LIMIT orders. Use --price.")
        return _parse_positive_float(price, "Price")

    if ot in ("STOP_MARKET", "STOP_LIMIT"):
        if price is None:
            raise ValueError(f"Stop price is required for {ot} orders. Use --price.")
        return _parse_positive_float(price, "Stop price")

    return None  # MARKET / TWAP — no price needed


def validate_stop_limit_price(limit_price: str | float | None) -> float:
    """Extra validator for STOP_LIMIT: the limit price after trigger."""
    if limit_price is None:
        raise ValueError("Limit price is required for STOP_LIMIT orders. Use --limit-price.")
    return _parse_positive_float(limit_price, "Limit price")


def validate_twap_slices(slices: int | str | None) -> int:
    if slices is None:
        return 5  # default
    try:
        s = int(slices)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid slices value '{slices}'. Must be an integer between 2 and 20.")
    if not (2 <= s <= 20):
        raise ValueError(f"Slices must be between 2 and 20, got {s}.")
    return s


def validate_twap_interval(interval: int | str | None) -> int:
    if interval is None:
        return 10  # default
    try:
        i = int(interval)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid interval '{interval}'. Must be seconds between 5 and 300.")
    if not (5 <= i <= 300):
        raise ValueError(f"Interval must be between 5 and 300 seconds, got {i}.")
    return i


def _parse_positive_float(value, label: str) -> float:
    try:
        p = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {label} '{value}'. Must be a positive number.")
    if p <= 0:
        raise ValueError(f"{label} must be greater than 0, got {p}.")
    return p
