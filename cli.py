#!/usr/bin/env python3
"""
cli.py - Binance Futures Demo Trading Bot CLI

Usage (direct flags):
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 80000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT --quantity 0.001 --price 75000 --limit-price 74900
  python cli.py --symbol BTCUSDT --side BUY --type TWAP --quantity 0.005 --slices 5 --interval 10
  python cli.py --balance
  python cli.py --menu
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
)
from bot.orders import place_stop_limit_order, place_twap_order
from bot.validators import (
    validate_symbol, validate_side, validate_order_type,
    validate_quantity, validate_price,
    validate_stop_limit_price, validate_twap_slices, validate_twap_interval,
)

# ── Credentials ───────────────────────────────────────────────────────────────

API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY",    "aq41M1eyRCrcUComd4OaciqoCeyCyDorWXQNzCzItFhnu1ihEl1NxKaS2ABN3Hj8")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "lzD0jgnlR9dCrlK6HiritbaBAlIsn8KihY3dwSsUnyYy2X038cDFm59UPkJbCKMQ")

# ── Credential check ──────────────────────────────────────────────────────────

def check_credentials():
    bad = {"PASTE_YOUR_API_KEY_HERE", "YOUR_API_KEY_HERE", "", None}
    if API_KEY in bad or API_SECRET in bad:
        print(
            "\n[ERROR] API credentials not configured.\n"
            "  Edit cli.py and paste your Demo Trading keys.\n"
            "  Or set environment variables:\n"
            "    PowerShell: $env:BINANCE_TESTNET_API_KEY='your_key'\n"
            "    PowerShell: $env:BINANCE_TESTNET_API_SECRET='your_secret'\n"
        )
        sys.exit(1)


# ── Separator helpers ─────────────────────────────────────────────────────────

def sep(char="-", width=52):
    print(char * width)

def header(title):
    sep("=")
    print(f"  {title}")
    sep("=")

def section(title):
    print(f"\n  -- {title} --")


# ── Balance display ───────────────────────────────────────────────────────────

def show_balance(client: BinanceFuturesClient):
    try:
        usdt  = client.get_balance("USDT")
        price = client.get_price("BTCUSDT")
        print(f"\n  Available USDT : ${usdt:,.2f}")
        print(f"  BTCUSDT price  : ${price:,.2f}\n")
    except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
        print(f"\n  [ERROR] {exc}\n")


# ── Order request summary ─────────────────────────────────────────────────────

def print_request_summary(symbol, side, order_type, quantity, price=None,
                           limit_price=None, tif="GTC", slices=None, interval=None):
    sep()
    print("  Order Request Summary")
    sep()
    print(f"  Symbol      : {symbol}")
    print(f"  Side        : {side}")
    print(f"  Type        : {order_type}")
    print(f"  Quantity    : {quantity}")
    if order_type == "LIMIT":
        print(f"  Limit Price : {price}")
        print(f"  TIF         : {tif}")
    elif order_type == "STOP_MARKET":
        print(f"  Stop Price  : {price}")
    elif order_type == "STOP_LIMIT":
        print(f"  Stop Price  : {price}  (trigger)")
        print(f"  Limit Price : {limit_price}  (fill price)")
        print(f"  TIF         : {tif}")
    elif order_type == "TWAP":
        print(f"  Slices      : {slices}")
        print(f"  Interval    : {interval}s")
        print(f"  Slice Qty   : {round(quantity / slices, 6)}")
    sep()


# ── Enhanced interactive MENU ─────────────────────────────────────────────────

def prompt(label: str, default: str = None) -> str:
    """Show prompt with optional default, validate non-empty."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val and default:
            return default
        if val:
            return val
        print(f"  [!] This field is required.")


def prompt_choice(label: str, choices: list[str], default: str = None) -> str:
    """Show numbered menu and return selected value."""
    print(f"\n  {label}")
    for i, c in enumerate(choices, 1):
        marker = " (default)" if c == default else ""
        print(f"    {i}. {c}{marker}")
    while True:
        raw = input("  Enter number or value: ").strip()
        if not raw and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        if raw.upper() in [c.upper() for c in choices]:
            return raw.upper()
        print(f"  [!] Invalid choice. Enter 1-{len(choices)} or one of {choices}.")


def run_menu(client: BinanceFuturesClient, log):
    """Full interactive menu — loops until user picks Exit."""
    header("Binance Futures Demo Trading Bot")
    show_balance(client)

    # ── Main loop ─────────────────────────────────────────────────────────
    while True:

        # Step 1: Main action
        action = prompt_choice(
            "What do you want to do?",
            ["Place Order", "Check Balance", "Exit"],
        )

        if action == "Exit":
            print("\n  Goodbye!\n")
            sys.exit(0)

        if action == "Check Balance":
            show_balance(client)
            continue  # back to top of loop

        # ── Place Order path (everything below is INSIDE the while loop) ──

        # Step 2: Symbol
        section("Step 1: Symbol")
        print(f"  Common symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT")
        while True:
            try:
                symbol = validate_symbol(prompt("Symbol", "BTCUSDT"))
                break
            except ValueError as e:
                print(f"  [!] {e}")

        # Step 3: Side
        section("Step 2: Side")
        side = prompt_choice("Order side?", ["BUY", "SELL"])

        # Step 4: Order type
        section("Step 3: Order Type")
        descriptions = {
            "MARKET":      "MARKET      - Fill immediately at best price",
            "LIMIT":       "LIMIT       - Place order at a specific price",
            "STOP_MARKET": "STOP_MARKET - Trigger a market order at stop price",
            "STOP_LIMIT":  "STOP_LIMIT  - Trigger a limit order at stop price  [BONUS]",
            "TWAP":        "TWAP        - Split into timed slices              [BONUS]",
        }
        type_choices = list(descriptions.keys())
        print()
        for i, (k, v) in enumerate(descriptions.items(), 1):
            print(f"    {i}. {v}")
        while True:
            raw = input("  Enter number or type: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(type_choices):
                order_type = type_choices[int(raw) - 1]
                break
            if raw.upper() in type_choices:
                order_type = raw.upper()
                break
            print(f"  [!] Enter 1-{len(type_choices)}.")

        # Step 5: Quantity
        section("Step 4: Quantity")
        while True:
            try:
                quantity = validate_quantity(prompt("Quantity (e.g. 0.001)"))
                break
            except ValueError as e:
                print(f"  [!] {e}")

        # Step 6: Prices (depends on order type)
        price = limit_price = None
        tif = "GTC"
        slices = 5
        interval = 10

        if order_type == "LIMIT":
            section("Step 5: Limit Price & TIF")
            while True:
                try:
                    price = validate_price(prompt("Limit price"), order_type)
                    break
                except ValueError as e:
                    print(f"  [!] {e}")
            tif = prompt_choice("Time-in-Force?", ["GTC", "IOC", "FOK"], default="GTC")

        elif order_type == "STOP_MARKET":
            section("Step 5: Stop Price")
            while True:
                try:
                    price = validate_price(prompt("Stop trigger price"), order_type)
                    break
                except ValueError as e:
                    print(f"  [!] {e}")

        elif order_type == "STOP_LIMIT":
            section("Step 5: Stop Price + Limit Price")
            print("  Stop price  = price that TRIGGERS the order")
            print("  Limit price = price at which the order is PLACED after trigger")
            while True:
                try:
                    price = validate_price(prompt("Stop trigger price"), order_type)
                    break
                except ValueError as e:
                    print(f"  [!] {e}")
            while True:
                try:
                    limit_price = validate_stop_limit_price(prompt("Limit fill price"))
                    break
                except ValueError as e:
                    print(f"  [!] {e}")
            tif = prompt_choice("Time-in-Force?", ["GTC", "IOC", "FOK"], default="GTC")

        elif order_type == "TWAP":
            section("Step 5: TWAP Settings")
            while True:
                try:
                    slices = validate_twap_slices(prompt("Number of slices (2-20)", "5"))
                    break
                except ValueError as e:
                    print(f"  [!] {e}")
            while True:
                try:
                    interval = validate_twap_interval(prompt("Seconds between slices (5-300)", "10"))
                    break
                except ValueError as e:
                    print(f"  [!] {e}")

        # Step 7: Confirm
        print()
        print_request_summary(
            symbol, side, order_type, quantity, price, limit_price, tif,
            slices if order_type == "TWAP" else None,
            interval if order_type == "TWAP" else None,
        )
        confirm = input("  Confirm and place order? [Y/n]: ").strip().lower()
        if confirm not in ("", "y", "yes"):
            print("\n  Order cancelled.\n")
            continue  # back to top of loop, don't exit

        # Step 8: Place order
        _execute_order(
            client, log, symbol, side, order_type, quantity,
            price, limit_price, tif, slices, interval,
        )
        # Loop continues — user is brought back to the main menu


# ── Order execution (shared by menu and CLI flags) ────────────────────────────

def _execute_order(client, log, symbol, side, order_type, quantity,
                   price=None, limit_price=None, tif="GTC", slices=5, interval=10):
    log.info("Submitting order | symbol=%s side=%s type=%s qty=%s", symbol, side, order_type, quantity)
    try:
        if order_type == "MARKET":
            summary = place_market_order(client, symbol, side, quantity)
            print_order_result(summary)

        elif order_type == "LIMIT":
            summary = place_limit_order(client, symbol, side, quantity, price, tif)
            print_order_result(summary)

        elif order_type == "STOP_MARKET":
            summary = place_stop_market_order(client, symbol, side, quantity, price)
            print_order_result(summary)

        elif order_type == "STOP_LIMIT":
            summary = place_stop_limit_order(client, symbol, side, quantity, price, limit_price, tif)
            print_order_result(summary)

        elif order_type == "TWAP":
            results = place_twap_order(client, symbol, side, quantity, slices, interval)
            log.info("TWAP complete | total_slices=%s filled=%s", slices, len(results))
            return

        log.info("Order completed | orderId=%s status=%s", summary["orderId"], summary["status"])

    except BinanceAPIError as exc:
        log.error("API error: code=%s msg=%s", exc.code, exc.message)
        print(f"\n  [API ERROR {exc.code}] {exc.message}")
        hints = {
            -2015: "Check your API key/secret and IP restrictions.",
            -1111: "Too many decimal places in quantity or price.",
            -1121: "Invalid symbol name (e.g. use BTCUSDT).",
            -4003: "Quantity too low -- check minimum lot size.",
            -2021: "Stop price must be below (SELL) or above (BUY) current price.",
        }
        if exc.code in hints:
            print(f"  Hint: {hints[exc.code]}")
        print()
        # Don't sys.exit in menu mode — just return so loop continues

    except (ConnectionError, TimeoutError) as exc:
        log.error("Network error: %s", exc)
        print(f"\n  [NETWORK ERROR] {exc}\n")

    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        print(f"\n  [ERROR] {exc}\n")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Demo Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--symbol",      type=str)
    p.add_argument("--side",        type=str)
    p.add_argument("--type",        type=str, dest="order_type",
                   help="MARKET | LIMIT | STOP_MARKET | STOP_LIMIT | TWAP")
    p.add_argument("--quantity",    type=float)
    p.add_argument("--price",       type=float, default=None,
                   help="Limit price (LIMIT), or stop trigger price (STOP_MARKET/STOP_LIMIT)")
    p.add_argument("--limit-price", type=float, default=None, dest="limit_price",
                   help="Limit fill price for STOP_LIMIT orders")
    p.add_argument("--tif",         type=str, default="GTC", choices=["GTC","IOC","FOK"])
    p.add_argument("--slices",      type=int, default=5,  help="TWAP: number of slices (default 5)")
    p.add_argument("--interval",    type=int, default=10, help="TWAP: seconds between slices (default 10)")
    p.add_argument("--balance",     action="store_true", help="Show balance and exit")
    p.add_argument("--menu",        action="store_true", help="Launch interactive menu")
    return p


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log    = setup_logging()
    check_credentials()
    parser = build_parser()
    args   = parser.parse_args()
    client = BinanceFuturesClient(API_KEY, API_SECRET)

    if args.balance:
        show_balance(client)
        return

    if args.menu or not any([args.symbol, args.side, args.order_type]):
        run_menu(client, log)
        return

    # Direct flag mode
    try:
        symbol      = validate_symbol(args.symbol or "")
        side        = validate_side(args.side or "")
        order_type  = validate_order_type(args.order_type or "")
        quantity    = validate_quantity(args.quantity or "")
        price       = validate_price(args.price, order_type)
        limit_price = None
        slices      = validate_twap_slices(args.slices)
        interval    = validate_twap_interval(args.interval)
        if order_type == "STOP_LIMIT":
            limit_price = validate_stop_limit_price(args.limit_price)
    except ValueError as exc:
        log.warning("Validation error: %s", exc)
        print(f"\n  [VALIDATION ERROR] {exc}\n")
        parser.print_help()
        sys.exit(1)

    tif = (args.tif or "GTC").upper()
    print_request_summary(symbol, side, order_type, quantity, price, limit_price, tif, slices, interval)
    _execute_order(client, log, symbol, side, order_type, quantity, price, limit_price, tif, slices, interval)


if __name__ == "__main__":
    main()