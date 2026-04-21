"""
orders.py
---------
High-level order placement functions.
Sits between the CLI layer and the raw API client.
"""

from __future__ import annotations

import logging
from typing import Optional

from .client import BinanceFuturesClient

log = logging.getLogger("trading_bot.orders")


def _extract_summary(order: dict) -> dict:
    """Pull the fields we care about from a raw API response."""
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


def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
) -> dict:
    log.info(
        "Placing MARKET %s order | symbol=%s qty=%s",
        side, symbol, quantity,
    )
    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=quantity,
    )
    summary = _extract_summary(raw)
    log.info("MARKET order placed successfully | %s", summary)
    return summary


def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = "GTC",
) -> dict:
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
    log.info("LIMIT order placed successfully | %s", summary)
    return summary


def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
) -> dict:
    """
    BONUS: Stop-Market order — triggers a market order when price hits stop_price.
    Useful for stop-loss / take-profit automation.
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
    log.info("STOP_MARKET order placed successfully | %s", summary)
    return summary


def print_order_result(summary: dict, success: bool = True) -> None:
    """Pretty-print the order result to stdout."""
    status_line = "ORDER PLACED SUCCESSFULLY" if success else "ORDER FAILED"
    sep = "─" * 50

    print(f"\n{sep}")
    print(f"  {status_line}")
    print(sep)
    print(f"  Order ID    : {summary.get('orderId', 'N/A')}")
    print(f"  Symbol      : {summary.get('symbol')}")
    print(f"  Side        : {summary.get('side')}")
    print(f"  Type        : {summary.get('type')}")
    print(f"  Qty         : {summary.get('origQty')}")
    print(f"  Executed Qty: {summary.get('executedQty')}")

    if summary.get("type") == "LIMIT":
        print(f"  Limit Price : {summary.get('price')}")
        print(f"  Avg Price   : {summary.get('avgPrice')}")
        print(f"  TIF         : {summary.get('timeInForce')}")
    elif summary.get("type") == "MARKET":
        print(f"  Avg Price   : {summary.get('avgPrice')}")
    elif summary.get("type") == "STOP_MARKET":
        print(f"  Stop Price  : {summary.get('stopPrice')}")

    print(f"  Status      : {summary.get('status')}")
    print(f"{sep}\n")
