"""
bot/orders.py
=============
High-level order placement functions.

This module sits between the CLI layer (cli.py) and the raw API client
(client.py). Each function:
  - Accepts validated, typed Python values
  - Builds the correct API parameter dict
  - Delegates the HTTP call to BinanceFuturesClient.place_order()
  - Extracts and returns a clean summary dict
  - Logs the action at INFO level for the audit trail

Supported order types
---------------------
  MARKET      : Fills immediately at best available price
  LIMIT       : Rests in the order book at a specified price
  STOP_MARKET : Triggers a market order when price hits stop_price
  STOP_LIMIT  : Triggers a limit order when price hits stop_price  [BONUS]
  TWAP        : Splits a large order into equal time-spaced slices  [BONUS]
"""

from __future__ import annotations

import logging
import time

from .client import BinanceFuturesClient

log = logging.getLogger("trading_bot.orders")


# ── Internal helper ───────────────────────────────────────────────────────────

def _extract_summary(order: dict) -> dict:
    """
    Pull the fields we care about from a raw Binance API response.

    The raw response contains many fields we don't need for display/logging.
    This normalises it to a consistent structure used by print_order_result().
    """
    return {
        "orderId":     order.get("orderId"),
        "symbol":      order.get("symbol"),
        "side":        order.get("side"),
        "type":        order.get("type"),
        "origQty":     order.get("origQty"),      # quantity originally requested
        "executedQty": order.get("executedQty"),  # quantity actually filled
        "avgPrice":    order.get("avgPrice"),      # average fill price
        "price":       order.get("price"),         # limit price (if applicable)
        "stopPrice":   order.get("stopPrice"),     # stop trigger price (if applicable)
        "status":      order.get("status"),        # NEW / FILLED / PARTIALLY_FILLED etc.
        "timeInForce": order.get("timeInForce"),   # GTC / IOC / FOK
    }


# ── MARKET order ──────────────────────────────────────────────────────────────

def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
) -> dict:
    """
    Place a MARKET order — fills immediately at the best available price.

    Parameters
    ----------
    client   : Authenticated BinanceFuturesClient instance
    symbol   : Trading pair, e.g. "BTCUSDT"
    side     : "BUY" or "SELL"
    quantity : Contract quantity (minimum 0.001 for BTCUSDT)

    Returns
    -------
    dict : Order summary with orderId, status, avgPrice, executedQty, etc.
    """
    log.info("Placing MARKET %s order | symbol=%s qty=%s", side, symbol, quantity)

    raw     = client.place_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
    summary = _extract_summary(raw)

    log.info("MARKET order accepted | orderId=%s status=%s", summary["orderId"], summary["status"])
    return summary


# ── LIMIT order ───────────────────────────────────────────────────────────────

def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = "GTC",
) -> dict:
    """
    Place a LIMIT order — rests in the order book until filled or cancelled.

    Parameters
    ----------
    client        : Authenticated BinanceFuturesClient instance
    symbol        : Trading pair, e.g. "BTCUSDT"
    side          : "BUY" or "SELL"
    quantity      : Contract quantity
    price         : Limit price — order will not fill above (BUY) or below (SELL) this
    time_in_force : How long the order stays active:
                      GTC (Good Till Cancelled) — stays until filled or manually cancelled
                      IOC (Immediate or Cancel)  — fills what it can, cancels the rest
                      FOK (Fill or Kill)          — must fill entirely or be cancelled

    Returns
    -------
    dict : Order summary. Status will be NEW if resting, FILLED if crossed the spread.
    """
    log.info(
        "Placing LIMIT %s order | symbol=%s qty=%s price=%s tif=%s",
        side, symbol, quantity, price, time_in_force,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="LIMIT",
        quantity=quantity,
        price=price,
        timeInForce=time_in_force,
    )
    summary = _extract_summary(raw)

    log.info("LIMIT order accepted | orderId=%s status=%s", summary["orderId"], summary["status"])
    return summary


# ── STOP_MARKET order ─────────────────────────────────────────────────────────

def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
) -> dict:
    """
    Place a STOP_MARKET order.

    When the market price reaches stop_price, a MARKET order is triggered.
    Commonly used as a stop-loss to limit downside risk.

    Note: stop_price must be BELOW current price for SELL, ABOVE for BUY.

    Parameters
    ----------
    client     : Authenticated BinanceFuturesClient instance
    symbol     : Trading pair, e.g. "BTCUSDT"
    side       : "BUY" or "SELL"
    quantity   : Contract quantity
    stop_price : Price that triggers the market order

    Returns
    -------
    dict : Order summary. Status will be NEW (waiting for trigger).
    """
    log.info(
        "Placing STOP_MARKET %s order | symbol=%s qty=%s stopPrice=%s",
        side, symbol, quantity, stop_price,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP_MARKET",
        quantity=quantity,
        stopPrice=stop_price,
    )
    summary = _extract_summary(raw)

    log.info("STOP_MARKET order accepted | orderId=%s status=%s", summary["orderId"], summary["status"])
    return summary


# ── STOP_LIMIT order (BONUS) ──────────────────────────────────────────────────

def place_stop_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
    limit_price: float,
    time_in_force: str = "GTC",
) -> dict:
    """
    BONUS: Place a Stop-Limit order.

    Two-phase execution:
      Phase 1: Order is dormant until market price reaches stop_price (trigger)
      Phase 2: A LIMIT order is placed at limit_price (fill price)

    Advantage over STOP_MARKET: you control the fill price — the order
    will not execute at a worse price than limit_price.

    Example — SELL stop_price=75000, limit_price=74900:
      When BTC falls to 75000, a limit sell at 74900 is placed.
      If the market drops past 74900 before filling, order stays open.

    Note: Binance Futures uses the type name "STOP" for stop-limit orders.

    Parameters
    ----------
    client        : Authenticated BinanceFuturesClient instance
    symbol        : Trading pair, e.g. "BTCUSDT"
    side          : "BUY" or "SELL"
    quantity      : Contract quantity
    stop_price    : Trigger price — activates the limit order
    limit_price   : Fill price — the price of the limit order once triggered
    time_in_force : GTC / IOC / FOK (applies to the triggered limit order)

    Returns
    -------
    dict : Order summary. Status will be NEW (waiting for trigger).
    """
    log.info(
        "Placing STOP_LIMIT %s order | symbol=%s qty=%s stopPrice=%s limitPrice=%s tif=%s",
        side, symbol, quantity, stop_price, limit_price, time_in_force,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP",            # Binance Futures API name for stop-limit
        quantity=quantity,
        price=limit_price,      # the limit fill price after trigger
        stopPrice=stop_price,   # the trigger price
        timeInForce=time_in_force,
    )
    summary = _extract_summary(raw)
    summary["limitPrice"] = limit_price   # add for display convenience

    log.info("STOP_LIMIT order accepted | orderId=%s status=%s", summary["orderId"], summary["status"])
    return summary


# ── TWAP order (BONUS) ────────────────────────────────────────────────────────

def place_twap_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    total_quantity: float,
    slices: int = 5,
    interval_seconds: int = 10,
) -> list[dict]:
    """
    BONUS: Execute a TWAP (Time-Weighted Average Price) order.

    Splits a large order into `slices` equal MARKET orders placed every
    `interval_seconds` seconds. This reduces market impact by spreading
    execution over time and typically achieves a price close to the
    time-weighted average.

    Example: Buy 0.05 BTC as 5 x 0.01 BTC every 10 seconds.

    Parameters
    ----------
    client           : Authenticated BinanceFuturesClient instance
    symbol           : Trading pair, e.g. "BTCUSDT"
    side             : "BUY" or "SELL"
    total_quantity   : Total amount to buy/sell across all slices
    slices           : Number of equal sub-orders (default 5, range 2–20)
    interval_seconds : Seconds to wait between slices (default 10, range 5–300)

    Returns
    -------
    list[dict] : One summary dict per successfully placed slice.
                 Failed slices are logged but not included in the return list.
    """
    slice_qty = round(total_quantity / slices, 6)
    results   = []

    log.info(
        "Starting TWAP %s | symbol=%s totalQty=%s slices=%s sliceQty=%s interval=%ss",
        side, symbol, total_quantity, slices, slice_qty, interval_seconds,
    )

    # Print progress header
    print(f"\n  [TWAP] Starting: {slices} slices of {slice_qty} {symbol[:3]} every {interval_seconds}s")
    print(f"  [TWAP] Total: {total_quantity} | Side: {side}")
    print(f"  {'Slice':<8} {'Status':<12} {'Avg Price':<14} {'Qty'}")
    print(f"  {'-'*48}")

    for i in range(1, slices + 1):
        try:
            raw     = client.place_order(symbol=symbol, side=side, type="MARKET", quantity=slice_qty)
            summary = _extract_summary(raw)
            results.append(summary)

            # Print per-slice progress row
            print(
                f"  {i}/{slices:<6} "
                f"{summary.get('status', '?'):<12} "
                f"{summary.get('avgPrice', 'N/A'):<14} "
                f"{summary.get('executedQty', slice_qty)}"
            )
            log.info("TWAP slice %s/%s placed | orderId=%s avgPrice=%s",
                     i, slices, summary["orderId"], summary.get("avgPrice"))

        except Exception as exc:
            # Log and continue — don't abort remaining slices on a single failure
            log.error("TWAP slice %s/%s failed: %s", i, slices, exc)
            print(f"  {i}/{slices:<6} FAILED       -- {exc}")

        # Wait before next slice (skip wait after the last slice)
        if i < slices:
            print(f"  [TWAP] Waiting {interval_seconds}s ...")
            time.sleep(interval_seconds)

    print(f"  {'-'*48}")
    print(f"  [TWAP] Done. {len(results)}/{slices} slices filled.\n")
    log.info("TWAP complete | symbol=%s side=%s filled=%s/%s", symbol, side, len(results), slices)
    return results


# ── Display helper ────────────────────────────────────────────────────────────

def print_order_result(summary: dict, success: bool = True) -> None:
    """
    Print a formatted order result to stdout.

    Adapts the displayed fields based on order type so only relevant
    information is shown (e.g. stop price for STOP orders, avg price
    for MARKET orders).

    Parameters
    ----------
    summary : Dict returned by one of the place_*_order() functions
    success : True = "ORDER PLACED SUCCESSFULLY", False = "ORDER FAILED"
    """
    status_line = "ORDER PLACED SUCCESSFULLY" if success else "ORDER FAILED"
    sep         = "-" * 50

    print(f"\n{sep}")
    print(f"  {status_line}")
    print(sep)
    print(f"  Order ID    : {summary.get('orderId', 'N/A')}")
    print(f"  Symbol      : {summary.get('symbol')}")
    print(f"  Side        : {summary.get('side')}")
    print(f"  Type        : {summary.get('type')}")
    print(f"  Qty         : {summary.get('origQty')}")
    print(f"  Executed Qty: {summary.get('executedQty')}")

    otype = summary.get("type", "")
    if otype == "LIMIT":
        print(f"  Limit Price : {summary.get('price')}")
        print(f"  Avg Price   : {summary.get('avgPrice')}")
        print(f"  TIF         : {summary.get('timeInForce')}")
    elif otype == "MARKET":
        print(f"  Avg Price   : {summary.get('avgPrice')}")
    elif otype == "STOP_MARKET":
        print(f"  Stop Price  : {summary.get('stopPrice')}")
    elif otype == "STOP":
        # Binance returns "STOP" for stop-limit orders
        print(f"  Stop Price  : {summary.get('stopPrice')}")
        print(f"  Limit Price : {summary.get('price')}")
        print(f"  TIF         : {summary.get('timeInForce')}")

    print(f"  Status      : {summary.get('status')}")
    print(f"{sep}\n")
