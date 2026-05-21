#!/usr/bin/env python3
"""
cli.py
======
Command-line entry point for the Binance Futures Testnet Trading Bot.

Two modes of operation
----------------------
1. Flag mode  : Pass all order details as command-line arguments.
                Best for scripting, testing, and quick one-off orders.

2. Menu mode  : Interactive step-by-step guided menu.
                Validates every input with re-prompts on invalid values.
                Loops back to the main menu after each action.
                Exits only when the user selects "Exit".

Usage examples (flag mode)
--------------------------
  python cli.py --balance
  python cli.py --symbol BTCUSDT --side BUY  --type MARKET     --quantity 0.001
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT       --quantity 0.001 --price 80000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 75000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT  --quantity 0.001 --price 75000 --limit-price 74900
  python cli.py --symbol BTCUSDT --side BUY  --type TWAP        --quantity 0.005 --slices 5 --interval 10

Usage examples (menu mode)
--------------------------
  python cli.py --menu
  python cli.py           # no arguments also launches the menu
"""

from __future__ import annotations

import argparse
import os
import sys

# Load .env file if present (no-op if the file doesn't exist)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; env vars can be set directly in the shell

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
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_limit_price,
    validate_twap_slices,
    validate_twap_interval,
)

# ── Credentials ───────────────────────────────────────────────────────────────
# Keys are loaded from the .env file (preferred) or from shell environment vars.
# Never hardcode keys here — use .env.example as a template.
API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY",    "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")


# ── Credential guard ──────────────────────────────────────────────────────────

def check_credentials() -> None:
    """
    Exit with a clear, actionable message if API credentials are missing.
    Called at startup before any API connection is made.
    """
    if not API_KEY or not API_SECRET:
        print(
            "\n[ERROR] API credentials not configured.\n"
            "\n  Option 1 — .env file (recommended):\n"
            "    1. Copy .env.example to .env\n"
            "    2. Paste your Testnet API key and secret into .env\n"
            "\n  Option 2 — Shell environment variables:\n"
            "    Linux/macOS : export BINANCE_TESTNET_API_KEY='your_key'\n"
            "                  export BINANCE_TESTNET_API_SECRET='your_secret'\n"
            "    Windows CMD : set BINANCE_TESTNET_API_KEY=your_key\n"
            "    PowerShell  : $env:BINANCE_TESTNET_API_KEY='your_key'\n"
            "\n  Get keys: https://testnet.binancefuture.com -> API Management\n"
        )
        sys.exit(1)


# ── Display helpers ───────────────────────────────────────────────────────────

def sep(char: str = "-", width: int = 52) -> None:
    """Print a horizontal separator line."""
    print(char * width)


def header(title: str) -> None:
    """Print a prominent section header."""
    sep("=")
    print(f"  {title}")
    sep("=")


def section(title: str) -> None:
    """Print a minor section label used inside the interactive menu."""
    print(f"\n  -- {title} --")


def show_balance(client: BinanceFuturesClient) -> None:
    """
    Fetch and print the available USDT balance and current BTCUSDT price.
    Catches API/network errors and prints them without crashing.
    """
    try:
        usdt  = client.get_balance("USDT")
        price = client.get_price("BTCUSDT")
        print(f"\n  Available USDT : ${usdt:,.2f}")
        print(f"  BTCUSDT price  : ${price:,.2f}\n")
    except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
        print(f"\n  [ERROR] {exc}\n")


def print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None = None,
    limit_price: float | None = None,
    tif: str = "GTC",
    slices: int | None = None,
    interval: int | None = None,
) -> None:
    """
    Print a formatted summary of the order parameters before submission.
    Shows only the fields relevant to the given order type.
    """
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


# ── Interactive menu helpers ──────────────────────────────────────────────────

def prompt(label: str, default: str = None) -> str:
    """
    Display a labelled input prompt and return the user's response.

    If `default` is provided, it is shown in brackets and returned if the
    user presses Enter without typing anything. Re-prompts on empty input
    when no default is set.
    """
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val and default:
            return default
        if val:
            return val
        print("  [!] This field is required.")


def prompt_choice(label: str, choices: list[str], default: str = None) -> str:
    """
    Display a numbered list of choices and return the selected value.

    Accepts either a number (1, 2, ...) or the choice text directly.
    Re-prompts on invalid input. Marks the default option if provided.
    """
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


# ── Interactive menu ──────────────────────────────────────────────────────────

def run_menu(client: BinanceFuturesClient, log) -> None:
    """
    Launch the full interactive guided menu.

    Flow:
      1. Show header and current balance
      2. Loop: prompt for action (Place Order / Check Balance / Exit)
         - Check Balance: refresh and display balance, loop back
         - Exit: print goodbye and exit the process
         - Place Order: collect all order parameters step by step,
           confirm, submit, then loop back to the top

    All input fields are validated with re-prompts on invalid values.
    API errors after submission are displayed but don't crash the menu —
    the user is returned to the main prompt to try again.
    """
    header("Binance Futures Testnet Trading Bot")
    show_balance(client)

    while True:

        # ── Main action selection ─────────────────────────────────────────
        action = prompt_choice(
            "What do you want to do?",
            ["Place Order", "Check Balance", "Exit"],
        )

        if action == "Exit":
            print("\n  Goodbye!\n")
            sys.exit(0)

        if action == "Check Balance":
            show_balance(client)
            continue

        # ── Place Order: collect parameters step by step ──────────────────

        # Step 1: Symbol
        section("Step 1: Symbol")
        print(f"  Common symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT")
        while True:
            try:
                symbol = validate_symbol(prompt("Symbol", "BTCUSDT"))
                break
            except ValueError as e:
                print(f"  [!] {e}")

        # Step 2: Side (BUY / SELL)
        section("Step 2: Side")
        side = prompt_choice("Order side?", ["BUY", "SELL"])

        # Step 3: Order type
        section("Step 3: Order Type")
        type_menu = {
            "MARKET":      "MARKET      - Fill immediately at best price",
            "LIMIT":       "LIMIT       - Place at a specific price",
            "STOP_MARKET": "STOP_MARKET - Trigger a market order at stop price",
            "STOP_LIMIT":  "STOP_LIMIT  - Trigger a limit order at stop price  [BONUS]",
            "TWAP":        "TWAP        - Split into equal timed slices         [BONUS]",
        }
        type_keys = list(type_menu.keys())
        print()
        for i, (k, v) in enumerate(type_menu.items(), 1):
            print(f"    {i}. {v}")
        while True:
            raw = input("  Enter number or type: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(type_keys):
                order_type = type_keys[int(raw) - 1]
                break
            if raw.upper() in type_keys:
                order_type = raw.upper()
                break
            print(f"  [!] Enter a number 1-{len(type_keys)}.")

        # Step 4: Quantity
        section("Step 4: Quantity")
        while True:
            try:
                quantity = validate_quantity(prompt("Quantity (e.g. 0.001)"))
                break
            except ValueError as e:
                print(f"  [!] {e}")

        # Step 5: Price fields — vary by order type
        price = limit_price = None
        tif      = "GTC"
        slices   = 5
        interval = 10

        if order_type == "LIMIT":
            section("Step 5: Limit Price & Time-in-Force")
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
            print("  Stop price  = triggers the order when market reaches this level")
            print("  Limit price = the price at which the order is actually placed")
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

        # Step 6: Confirmation
        print()
        print_request_summary(
            symbol, side, order_type, quantity, price, limit_price, tif,
            slices   if order_type == "TWAP" else None,
            interval if order_type == "TWAP" else None,
        )
        confirm = input("  Confirm and place order? [Y/n]: ").strip().lower()
        if confirm not in ("", "y", "yes"):
            print("\n  Order cancelled.\n")
            continue

        # Step 7: Submit order
        _execute_order(
            client, log, symbol, side, order_type, quantity,
            price, limit_price, tif, slices, interval,
        )


# ── Order execution ───────────────────────────────────────────────────────────

def _execute_order(
    client,
    log,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None = None,
    limit_price: float | None = None,
    tif: str = "GTC",
    slices: int = 5,
    interval: int = 10,
) -> None:
    """
    Route validated order parameters to the correct placement function.

    Shared by both menu mode and direct flag mode. Handles all exceptions
    from the API and network layer, printing friendly messages and hints
    without propagating exceptions (in menu mode the loop continues;
    in flag mode the process exits after this function returns).
    """
    log.info(
        "Submitting order | symbol=%s side=%s type=%s qty=%s",
        symbol, side, order_type, quantity,
    )

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
            summary = place_stop_limit_order(
                client, symbol, side, quantity, price, limit_price, tif
            )
            print_order_result(summary)

        elif order_type == "TWAP":
            results = place_twap_order(client, symbol, side, quantity, slices, interval)
            log.info("TWAP complete | symbol=%s slices=%s filled=%s", symbol, slices, len(results))
            return  # TWAP prints its own progress table

        log.info(
            "Order completed | orderId=%s status=%s",
            summary["orderId"], summary["status"],
        )

    except BinanceAPIError as exc:
        hints = {
            -2015: "Check your API key/secret and IP restriction settings.",
            -1111: "Too many decimal places in quantity or price.",
            -1121: "Invalid symbol — use a valid pair like BTCUSDT.",
            -4003: "Quantity below minimum lot size (BTCUSDT minimum: 0.001).",
            -2021: "Stop price direction wrong: must be below market for SELL, above for BUY.",
            -4016: "Price outside allowed range — check current market price.",
        }
        log.error("API error: code=%s msg=%s", exc.code, exc.message)
        print(f"\n  [API ERROR {exc.code}] {exc.message}")
        if exc.code in hints:
            print(f"  Hint: {hints[exc.code]}")
        print()

    except ConnectionError as exc:
        log.error("Network connection error: %s", exc)
        print(f"\n  [NETWORK ERROR] {exc}\n")

    except TimeoutError as exc:
        log.error("Request timed out: %s", exc)
        print(f"\n  [TIMEOUT ERROR] {exc}\n")

    except Exception as exc:
        log.exception("Unexpected error placing order: %s", exc)
        print(f"\n  [UNEXPECTED ERROR] {exc}\n")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argparse parser for flag mode."""
    p = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    p.add_argument("--symbol",      type=str,   help="Trading pair, e.g. BTCUSDT")
    p.add_argument("--side",        type=str,   help="BUY or SELL")
    p.add_argument("--type",        type=str,   dest="order_type",
                   help="MARKET | LIMIT | STOP_MARKET | STOP_LIMIT | TWAP")
    p.add_argument("--quantity",    type=float, help="Contract quantity")
    p.add_argument("--price",       type=float, default=None,
                   help="Limit price (LIMIT) or stop trigger price (STOP_MARKET / STOP_LIMIT)")
    p.add_argument("--limit-price", type=float, default=None, dest="limit_price",
                   help="Limit fill price for STOP_LIMIT orders")
    p.add_argument("--tif",         type=str,   default="GTC",
                   choices=["GTC", "IOC", "FOK"],
                   help="Time-in-force for LIMIT / STOP_LIMIT (default: GTC)")
    p.add_argument("--slices",   type=int, default=5,
                   help="TWAP: number of equal slices, 2-20 (default: 5)")
    p.add_argument("--interval", type=int, default=10,
                   help="TWAP: seconds between slices, 5-300 (default: 10)")
    p.add_argument("--balance", action="store_true",
                   help="Show available USDT balance and current BTC price, then exit")
    p.add_argument("--menu",    action="store_true",
                   help="Launch the interactive guided menu")

    return p


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """
    Main entry point.

    Execution flow:
      1. Set up logging (console + rotating file)
      2. Validate credentials — exit early with clear message if missing
      3. Parse arguments
      4. Create the API client
      5. Route to: balance display / interactive menu / direct flag mode
    """
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

    # ── Direct flag mode ──────────────────────────────────────────────────
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
        log.warning("Input validation failed: %s", exc)
        print(f"\n  [VALIDATION ERROR] {exc}\n")
        parser.print_help()
        sys.exit(1)

    tif = (args.tif or "GTC").upper()

    print_request_summary(symbol, side, order_type, quantity, price, limit_price, tif, slices, interval)
    _execute_order(
        client, log, symbol, side, order_type, quantity,
        price, limit_price, tif, slices, interval,
    )


if __name__ == "__main__":
    main()
