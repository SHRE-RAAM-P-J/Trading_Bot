"""
orders.py
---------
High-level order placement functions.
Sits between the CLI layer and the raw API client.

Order types supported:
  - MARKET
  - LIMIT
  - STOP_MARKET
  - STOP (Stop-Limit)   [BONUS]
  - TWAP                [BONUS - splits large order into timed slices]
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .client import BinanceFuturesClient

log = logging.getLogger("trading_bot.orders")


def _extract_summary(order: dict) -> dict:
    return {
        "orderId":     order.get("orderId"),
        "symbol":      order.get("symbol"),
        "side":        order.get("side"),
        "type":        order.get("type"),
        "origQty":     order.get("origQty"),
        "executedQty": order.get("executedQty"),
        "avgPrice":    order.get("avgPrice"),
        "price":       order.get("price"),
        "stopPrice":   order.get("stopPrice"),
        "status":      order.get("status"),
        "timeInForce": order.get("timeInForce"),
    }


def place_market_order(client, symbol, side, quantity):
    log.info("Placing MARKET %s order | symbol=%s qty=%s", side, symbol, quantity)
    raw = client.place_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
    summary = _extract_summary(raw)
    log.info("MARKET order placed successfully | %s", summary)
    return summary


def place_limit_order(client, symbol, side, quantity, price, time_in_force="GTC"):
    log.info("Placing LIMIT %s order | symbol=%s qty=%s price=%s tif=%s", side, symbol, quantity, price, time_in_force)
    raw = client.place_order(symbol=symbol, side=side, type="LIMIT", quantity=quantity, price=price, timeInForce=time_in_force)
    summary = _extract_summary(raw)
    log.info("LIMIT order placed successfully | %s", summary)
    return summary


def place_stop_market_order(client, symbol, side, quantity, stop_price):
    log.info("Placing STOP_MARKET %s order | symbol=%s qty=%s stopPrice=%s", side, symbol, quantity, stop_price)
    raw = client.place_order(symbol=symbol, side=side, type="STOP_MARKET", quantity=quantity, stopPrice=stop_price)
    summary = _extract_summary(raw)
    log.info("STOP_MARKET order placed successfully | %s", summary)
    return summary


def place_stop_limit_order(client, symbol, side, quantity, stop_price, limit_price, time_in_force="GTC"):
    """
    BONUS order type: Stop-Limit.
    When market hits stop_price, a LIMIT order is placed at limit_price.
    More price control than STOP_MARKET (won't fill below your limit).

    Example: SELL stop=75000 limit=74900
      -> BTC drops to 75000 -> limit sell at 74900 is placed
    """
    log.info("Placing STOP_LIMIT %s order | symbol=%s qty=%s stopPrice=%s limitPrice=%s", side, symbol, quantity, stop_price, limit_price)
    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP",           # Binance futures uses "STOP" for stop-limit
        quantity=quantity,
        price=limit_price,     # limit price after trigger
        stopPrice=stop_price,  # trigger price
        timeInForce=time_in_force,
    )
    summary = _extract_summary(raw)
    summary["limitPrice"] = limit_price
    log.info("STOP_LIMIT order placed successfully | %s", summary)
    return summary


def place_twap_order(client, symbol, side, total_quantity, slices=5, interval_seconds=10):
    """
    BONUS order type: TWAP (Time-Weighted Average Price).
    Splits a large order into equal slices placed at intervals.
    Reduces market impact and averages out the entry price.

    Example: Buy 0.05 BTC as 5 x 0.01 BTC every 10 seconds.
    """
    slice_qty = round(total_quantity / slices, 6)
    results = []

    log.info("Starting TWAP %s | symbol=%s totalQty=%s slices=%s sliceQty=%s interval=%ss",
             side, symbol, total_quantity, slices, slice_qty, interval_seconds)

    print(f"\n  [TWAP] Starting: {slices} slices of {slice_qty} {symbol[:3]} every {interval_seconds}s")
    print(f"  [TWAP] Total: {total_quantity} | Side: {side}")
    print(f"  {'Slice':<8} {'Status':<12} {'Avg Price':<14} {'Qty'}")
    print(f"  {'-'*48}")

    for i in range(1, slices + 1):
        try:
            raw = client.place_order(symbol=symbol, side=side, type="MARKET", quantity=slice_qty)
            summary = _extract_summary(raw)
            results.append(summary)
            print(f"  {i}/{slices:<6} {summary.get('status','?'):<12} {summary.get('avgPrice','N/A'):<14} {summary.get('executedQty', slice_qty)}")
            log.info("TWAP slice %s/%s placed | orderId=%s", i, slices, summary["orderId"])
        except Exception as exc:
            log.error("TWAP slice %s/%s failed: %s", i, slices, exc)
            print(f"  {i}/{slices:<6} FAILED       -- {exc}")

        if i < slices:
            print(f"  [TWAP] Waiting {interval_seconds}s ...")
            time.sleep(interval_seconds)

    print(f"  {'-'*48}")
    print(f"  [TWAP] Done. {len(results)}/{slices} slices filled.\n")
    log.info("TWAP complete | filled=%s/%s", len(results), slices)
    return results


def print_order_result(summary: dict, success: bool = True) -> None:
    status_line = "ORDER PLACED SUCCESSFULLY" if success else "ORDER FAILED"
    sep = "-" * 50
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
        print(f"  Stop Price  : {summary.get('stopPrice')}")
        print(f"  Limit Price : {summary.get('price')}")
        print(f"  TIF         : {summary.get('timeInForce')}")
    print(f"  Status      : {summary.get('status')}")
    print(f"{sep}\n")
