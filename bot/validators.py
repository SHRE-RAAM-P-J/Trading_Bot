"""
bot/validators.py
=================
Pure input validation functions for the CLI layer.

Design principles:
  - Each function takes raw input (string or None) and returns a clean,
    typed Python value, or raises ValueError with a clear message.
  - No side effects — no API calls, no logging, no prints.
  - Validators are called before any order is submitted so errors are
    caught early with helpful messages rather than cryptic API errors.

Exception handling contract:
  Raises ValueError with a human-readable message on any invalid input.
  The CLI layer catches these and re-prompts in menu mode, or prints
  them with --help in flag mode.
"""

from __future__ import annotations

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_SIDES       = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT", "TWAP"}

# Shown as hints when an unrecognised symbol is entered
COMMON_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


# ── Symbol validators ─────────────────────────────────────────────────────────

def validate_symbol(symbol: str) -> str:
    """
    Validate a futures trading symbol by format.

    Checks:
      - Non-empty
      - Alphanumeric only (no slashes, hyphens, spaces)
      - At least 5 characters
      - Ends with a recognised quote currency (USDT, USDC, BUSD, BTC)

    Returns the symbol in uppercase.
    """
    s = symbol.strip().upper()

    if not s:
        raise ValueError("Symbol cannot be empty. Example: BTCUSDT")

    if not s.isalnum():
        raise ValueError(
            f"Invalid symbol '{symbol}'. Use letters and numbers only, e.g. BTCUSDT."
        )

    if len(s) < 5:
        raise ValueError(
            f"Symbol '{s}' is too short. Futures symbols look like BTCUSDT, ETHUSDT.\n"
            f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
        )

    # Futures pairs always end with a quote currency
    valid_suffixes = ("USDT", "USDC", "BUSD", "BTC")
    if not any(s.endswith(suffix) for suffix in valid_suffixes):
        raise ValueError(
            f"Symbol '{s}' doesn't look like a futures pair.\n"
            f"  Futures symbols end with USDT, USDC, or BTC — e.g. BTCUSDT, ETHUSDT.\n"
            f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
        )

    return s


def validate_symbol_live(symbol: str, client) -> str:
    """
    Validate a symbol by checking it against the live exchange info.

    Performs the format check first, then queries /fapi/v1/exchangeInfo
    to confirm the symbol actually exists on the testnet.

    Falls back silently to format-only validation if the API call fails,
    so connectivity issues don't block the user from submitting orders.

    Parameters
    ----------
    symbol : Raw symbol string from user input
    client : BinanceFuturesClient instance (used for the API call)

    Returns the symbol in uppercase if valid.
    """
    s = validate_symbol(symbol)  # format check first — fast and no network needed

    try:
        data      = client._get("/fapi/v1/exchangeInfo")
        valid_set = {item["symbol"] for item in data.get("symbols", [])}

        if s not in valid_set:
            # Suggest symbols that share the same base currency prefix
            suggestions = [v for v in valid_set if v.startswith(s[:3])][:5]
            hint = f"  Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            raise ValueError(
                f"Symbol '{s}' not found on Binance Futures.\n{hint}\n"
                f"  Common symbols: {', '.join(COMMON_SYMBOLS)}"
            )

    except ValueError:
        raise  # re-raise validation errors as-is
    except Exception:
        pass   # silently skip live check on any other error (network, parsing, etc.)

    return s


# ── Order field validators ────────────────────────────────────────────────────

def validate_side(side: str) -> str:
    """
    Validate the order side.

    Accepted values: BUY, SELL (case-insensitive).
    Returns the side in uppercase.
    """
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return s


def validate_order_type(order_type: str) -> str:
    """
    Validate the order type.

    Accepted values: MARKET, LIMIT, STOP_MARKET, STOP_LIMIT, TWAP (case-insensitive).
    Returns the order type in uppercase.
    """
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'.\n"
            f"  Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return t


def validate_quantity(quantity: str | float) -> float:
    """
    Validate the order quantity.

    Must be a positive number. The minimum lot size for BTCUSDT is 0.001.
    Returns a float.
    """
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid quantity '{quantity}'. Must be a positive number, e.g. 0.001."
        )
    if q <= 0:
        raise ValueError(f"Quantity must be greater than 0, got {q}.")
    return q


def validate_price(price: str | float | None, order_type: str) -> float | None:
    """
    Validate the primary price field.

    Rules by order type:
      LIMIT       : required — the price at which the order rests in the book
      STOP_MARKET : required — the stop trigger price
      STOP_LIMIT  : required — the stop trigger price (limit fill price is separate)
      MARKET/TWAP : not needed — returns None

    Returns a positive float, or None for order types that don't use a price.
    """
    ot = order_type.upper()

    if ot == "LIMIT":
        if price is None:
            raise ValueError("Price is required for LIMIT orders. Use --price.")
        return _parse_positive_float(price, "Price")

    if ot in ("STOP_MARKET", "STOP_LIMIT"):
        if price is None:
            raise ValueError(
                f"Stop trigger price is required for {ot} orders. Use --price."
            )
        return _parse_positive_float(price, "Stop price")

    return None  # MARKET and TWAP do not use a price field


def validate_stop_limit_price(limit_price: str | float | None) -> float:
    """
    Validate the limit fill price for STOP_LIMIT orders.

    This is separate from validate_price() because STOP_LIMIT orders
    require two prices: a stop trigger price (--price) and a limit fill
    price (--limit-price). Both must be validated independently.

    Returns a positive float.
    """
    if limit_price is None:
        raise ValueError(
            "Limit fill price is required for STOP_LIMIT orders. Use --limit-price."
        )
    return _parse_positive_float(limit_price, "Limit price")


# ── TWAP-specific validators ──────────────────────────────────────────────────

def validate_twap_slices(slices: int | str | None) -> int:
    """
    Validate the number of TWAP slices.

    Must be an integer between 2 and 20.
    Returns the default value of 5 if None is passed.
    """
    if slices is None:
        return 5  # default

    try:
        s = int(slices)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid slices value '{slices}'. Must be an integer between 2 and 20."
        )

    if not (2 <= s <= 20):
        raise ValueError(f"Slices must be between 2 and 20, got {s}.")

    return s


def validate_twap_interval(interval: int | str | None) -> int:
    """
    Validate the interval between TWAP slices in seconds.

    Must be an integer between 5 and 300.
    Returns the default value of 10 if None is passed.
    """
    if interval is None:
        return 10  # default

    try:
        i = int(interval)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid interval '{interval}'. Must be seconds between 5 and 300."
        )

    if not (5 <= i <= 300):
        raise ValueError(f"Interval must be between 5 and 300 seconds, got {i}.")

    return i


# ── Shared helper ─────────────────────────────────────────────────────────────

def _parse_positive_float(value: str | float, label: str) -> float:
    """
    Parse a value as a positive float, raising ValueError with a clear
    label in the message if parsing fails or value is not positive.

    Used internally by validate_price() and validate_stop_limit_price().
    """
    try:
        p = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid {label} '{value}'. Must be a positive number."
        )

    if p <= 0:
        raise ValueError(f"{label} must be greater than 0, got {p}.")

    return p
