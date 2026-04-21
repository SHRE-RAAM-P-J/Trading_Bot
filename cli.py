#!/usr/bin/env python3
"""
cli.py — CLI entry point for the Binance Futures Testnet Trading Bot.

Usage examples
--------------
# Market BUY
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# Limit SELL
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 80000

# Stop-Market BUY (bonus order type)
python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --price 70000

# Show account balance only
python cli.py --balance

# Interactive mode (prompts for all fields)
python cli.py --interactive
"""

from __future__ import annotations

import argparse
import os
import sys

from bot import (
    setup_logging,
    BinanceFuturesClient,
    BinanceAPIError,
    place_market_order,
    place_limit_order,
    place_stop_market_order,
    print_order_result,
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
)

# ── Credentials ───────────────────────────────────────────────────────────────
# Set these here OR export as environment variables before running.
API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY",    "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_credentials():
    placeholders = {"PASTE_YOUR_API_KEY_HERE", "YOUR_API_KEY_HERE", "", None}
    if API_KEY in placeholders or API_SECRET in {"PASTE_YOUR_API_SECRET_HERE", "YOUR_API_SECRET_HERE", "", None}:
        print(
            "\n[ERROR] API credentials not configured.\n"
            "  Edit cli.py and paste your Testnet keys, or set environment variables:\n"
            "    Windows CMD:   set BINANCE_TESTNET_API_KEY=your_key\n"
            "    PowerShell:    $env:BINANCE_TESTNET_API_KEY='your_key'\n"
            "    Linux/macOS:   export BINANCE_TESTNET_API_KEY=your_key\n"
            "  Keys: https://testnet.binancefuture.com → API Management\n"
        )
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--symbol",      type=str,   help="Trading pair, e.g. BTCUSDT")
    p.add_argument("--side",        type=str,   help="BUY or SELL")
    p.add_argument("--type",        type=str,   dest="order_type", help="MARKET | LIMIT | STOP_MARKET")
    p.add_argument("--quantity",    type=float, help="Contract quantity")
    p.add_argument("--price",       type=float, default=None, help="Limit / stop price")
    p.add_argument("--tif",         type=str,   default="GTC",
                   choices=["GTC", "IOC", "FOK"], help="Time-in-force for LIMIT (default: GTC)")
    p.add_argument("--balance",     action="store_true", help="Show account balance and exit")
    p.add_argument("--interactive", action="store_true", help="Prompt for all inputs interactively")
    return p


def interactive_prompt() -> argparse.Namespace:
    """Walk the user through order fields one by one."""
    print("\n── Interactive Order Entry ─────────────────────")

    symbol = input("  Symbol     [e.g. BTCUSDT]: ").strip()
    side   = input("  Side       [BUY/SELL]    : ").strip()
    otype  = input("  Order type [MARKET/LIMIT/STOP_MARKET]: ").strip()
    qty    = input("  Quantity               : ").strip()

    price = None
    if otype.upper() in ("LIMIT", "STOP_MARKET"):
        price = input("  Price (limit/stop)     : ").strip()

    tif = "GTC"
    if otype.upper() == "LIMIT":
        tif = input("  Time-in-force [GTC/IOC/FOK] (default GTC): ").strip() or "GTC"

    print("────────────────────────────────────────────────\n")

    ns = argparse.Namespace(
        symbol=symbol,
        side=side,
        order_type=otype,
        quantity=qty,
        price=price,
        tif=tif,
        balance=False,
        interactive=False,
    )
    return ns


def print_request_summary(symbol, side, order_type, quantity, price, tif):
    print("\n── Order Request ───────────────────────────────")
    print(f"  Symbol      : {symbol}")
    print(f"  Side        : {side}")
    print(f"  Type        : {order_type}")
    print(f"  Quantity    : {quantity}")
    if price:
        label = "Stop Price" if order_type == "STOP_MARKET" else "Price"
        print(f"  {label:<12}: {price}")
    if order_type == "LIMIT":
        print(f"  Time-in-Force: {tif}")
    print("────────────────────────────────────────────────")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log = setup_logging()
    check_credentials()

    parser = build_parser()
    args   = parser.parse_args()

    client = BinanceFuturesClient(API_KEY, API_SECRET)

    # ── Balance-only mode ────────────────────────────────────────────────
    if args.balance:
        try:
            balance = client.get_balance("USDT")
            price   = client.get_price("BTCUSDT")
            print(f"\n  Available USDT balance : ${balance:,.2f}")
            print(f"  BTCUSDT current price  : ${price:,.2f}\n")
        except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
            log.error("Failed to fetch balance: %s", exc)
            print(f"\n[ERROR] {exc}\n")
            sys.exit(1)
        return

    # ── Interactive mode ─────────────────────────────────────────────────
    if args.interactive or not any([args.symbol, args.side, args.order_type]):
        args = interactive_prompt()

    # ── Validate inputs ──────────────────────────────────────────────────
    try:
        symbol     = validate_symbol(args.symbol or "")
        side       = validate_side(args.side or "")
        order_type = validate_order_type(args.order_type or "")
        quantity   = validate_quantity(args.quantity or "")
        price      = validate_price(args.price, order_type)
    except ValueError as exc:
        log.warning("Validation error: %s", exc)
        print(f"\n[VALIDATION ERROR] {exc}\n")
        parser.print_help()
        sys.exit(1)

    tif = (args.tif or "GTC").upper()

    print_request_summary(symbol, side, order_type, quantity, price, tif)

    # ── Place order ──────────────────────────────────────────────────────
    log.info(
        "Submitting order | symbol=%s side=%s type=%s qty=%s price=%s",
        symbol, side, order_type, quantity, price,
    )
    try:
        if order_type == "MARKET":
            summary = place_market_order(client, symbol, side, quantity)

        elif order_type == "LIMIT":
            summary = place_limit_order(client, symbol, side, quantity, price, tif)

        elif order_type == "STOP_MARKET":
            summary = place_stop_market_order(client, symbol, side, quantity, price)

        else:
            raise ValueError(f"Unhandled order type: {order_type}")

        print_order_result(summary, success=True)
        log.info("Order completed | orderId=%s status=%s", summary["orderId"], summary["status"])

    except BinanceAPIError as exc:
        log.error("API error placing order: code=%s msg=%s", exc.code, exc.message)
        print(f"\n[API ERROR {exc.code}] {exc.message}\n")

        # Common error codes with friendly hints
        hints = {
            -2015: "Check your API key/secret — see README.md §Credentials.",
            -1111: "Too many decimal places in quantity or price.",
            -1121: "Invalid symbol — check the symbol name (e.g. BTCUSDT).",
            -4003: "Quantity too low — check the minimum lot size for this symbol.",
        }
        if exc.code in hints:
            print(f"  Hint: {hints[exc.code]}\n")
        sys.exit(1)

    except (ConnectionError, TimeoutError) as exc:
        log.error("Network error: %s", exc)
        print(f"\n[NETWORK ERROR] {exc}\n")
        sys.exit(1)

    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        print(f"\n[UNEXPECTED ERROR] {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
