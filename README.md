# Binance Futures Demo Trading Bot

A clean, production-structured Python CLI app for placing orders on
**Binance USDT-M Futures Demo Trading**. Uses direct REST calls — no
third-party Binance SDK required.

---

## Project Structure

```
Trading_Bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Low-level REST client (HMAC auth, signing, HTTP)
│   ├── orders.py            # Order placement logic (all 5 order types)
│   ├── validators.py        # Input validation with clear error messages
│   └── logging_config.py   # Rotating file + console log setup
├── cli.py                   # CLI entry point (flags + interactive menu)
├── logs/
│   └── trading_bot.log      # Auto-created on first run
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Prerequisites

- Python 3.9 or higher
- `pip` package manager

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Only one dependency: `requests`.

### 3. Get Demo Trading API credentials

> **Important:** This bot uses **Binance Futures Demo Trading**, not the
> old `testnet.binancefuture.com`. You need a real Binance account.

1. Log in to your Binance account at **https://www.binance.com**
2. Go to **Futures → Demo Trading** (or visit the demo site directly)
3. Click your profile icon → **API Management**
4. Click **Create API** → choose **System Generated**
5. Give it a name (e.g. `trading_bot`) and complete 2FA verification
6. On the key detail page, make sure **Enable Futures** is checked
7. Set **IP Access Restriction** to **Unrestricted**
8. Copy **both** the API Key and Secret Key — the secret is shown **only once**

### 4. Set your credentials

Open `cli.py` and replace the two placeholder lines near the top:

```python
API_KEY    = "PASTE_YOUR_API_KEY_HERE"
API_SECRET = "PASTE_YOUR_API_SECRET_HERE"
```

**Or use environment variables (more secure):**

```bash
# Windows PowerShell
$env:BINANCE_TESTNET_API_KEY    = "your_api_key"
$env:BINANCE_TESTNET_API_SECRET = "your_api_secret"

# Windows CMD
set BINANCE_TESTNET_API_KEY=your_api_key
set BINANCE_TESTNET_API_SECRET=your_api_secret

# Linux / macOS
export BINANCE_TESTNET_API_KEY=your_api_key
export BINANCE_TESTNET_API_SECRET=your_api_secret
```

---

## How to Run

All commands are run from the project root directory.

### Interactive menu (recommended)

```bash
python cli.py --menu
```

Launches a guided step-by-step menu. Validates every input before
submitting. Loops back to the main menu after each action — stays open
until you select Exit.

```
====================================================
  Binance Futures Demo Trading Bot
====================================================
  Available USDT : $5,000.00
  BTCUSDT price  : $78,110.40

  What do you want to do?
    1. Place Order
    2. Check Balance
    3. Exit
  Enter number or value:
```

Or just run with no arguments — the menu launches automatically:

```bash
python cli.py
```

---

### Direct flag mode (for scripting / automation)

#### Check account balance

```bash
python cli.py --balance
```

#### Market BUY

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

#### Limit SELL

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 80000
```

#### Stop-Market SELL

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 75000
```

#### Stop-Limit SELL *(Bonus)*

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \
  --quantity 0.001 --price 75000 --limit-price 74900
```

`--price` = stop trigger price, `--limit-price` = limit fill price after trigger.

#### TWAP BUY *(Bonus)*

```bash
python cli.py --symbol BTCUSDT --side BUY --type TWAP \
  --quantity 0.005 --slices 5 --interval 10
```

Splits 0.005 BTC into 5 market orders of 0.001 BTC placed every 10 seconds.

#### Full help

```bash
python cli.py --help
```

---

## Example Output

**Market order:**
```
----------------------------------------------------
  Order Request Summary
----------------------------------------------------
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Quantity    : 0.001
----------------------------------------------------

----------------------------------------------------
  ORDER PLACED SUCCESSFULLY
----------------------------------------------------
  Order ID    : 13057093602
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Qty         : 0.0010
  Executed Qty: 0.0010
  Avg Price   : 78110.40
  Status      : FILLED
----------------------------------------------------
```

**TWAP order:**
```
  [TWAP] Starting: 5 slices of 0.001 BTC every 10s
  [TWAP] Total: 0.005 | Side: BUY
  Slice    Status       Avg Price      Qty
  ------------------------------------------------
  1/5      FILLED       78110.40       0.001
  [TWAP] Waiting 10s ...
  2/5      FILLED       78098.20       0.001
  ...
  [TWAP] Done. 5/5 slices filled.
```

---

## Supported Order Types

| Type          | Required flags                              | Notes                                        |
|---------------|---------------------------------------------|----------------------------------------------|
| `MARKET`      | `--symbol --side --quantity`                | Fills immediately at best available price    |
| `LIMIT`       | `--symbol --side --quantity --price`        | Rests in order book until filled or cancelled|
| `STOP_MARKET` | `--symbol --side --quantity --price`        | `--price` = stop trigger, fills at market    |
| `STOP_LIMIT`  | `--symbol --side --quantity --price --limit-price` | Trigger + controlled fill price *(Bonus)* |
| `TWAP`        | `--symbol --side --quantity --slices --interval`   | Timed equal slices *(Bonus)*              |

---

## All CLI Flags

| Flag             | Type    | Description                                              |
|------------------|---------|----------------------------------------------------------|
| `--symbol`       | string  | Trading pair, e.g. `BTCUSDT`                             |
| `--side`         | string  | `BUY` or `SELL`                                          |
| `--type`         | string  | Order type (see table above)                             |
| `--quantity`     | float   | Contract quantity                                        |
| `--price`        | float   | Limit price (LIMIT) or stop trigger price (STOP orders)  |
| `--limit-price`  | float   | Limit fill price for `STOP_LIMIT` orders                 |
| `--tif`          | string  | Time-in-force: `GTC` (default), `IOC`, `FOK`            |
| `--slices`       | int     | TWAP: number of slices, 2–20 (default `5`)               |
| `--interval`     | int     | TWAP: seconds between slices, 5–300 (default `10`)       |
| `--balance`      | flag    | Show USDT balance and current BTC price, then exit       |
| `--menu`         | flag    | Launch interactive guided menu                           |

---

## Logging

Logs are written automatically to `logs/trading_bot.log`.

- **Console** — INFO level and above (clean, human-readable)
- **File** — DEBUG level (full request params, response body, timestamps)

The log file rotates at 5 MB and keeps 3 backups. Every order, error,
and API call is recorded with a timestamp.

Sample log entry:
```
2026-04-21 14:40:05  [INFO    ]  trading_bot.orders  Placing MARKET BUY order | symbol=BTCUSDT qty=0.001
2026-04-21 14:40:06  [DEBUG   ]  trading_bot.client  <- HTTP 200  body={"orderId":13057093602,...}
2026-04-21 14:40:06  [INFO    ]  trading_bot  Order completed | orderId=13057093602 status=FILLED
```

---

## Error Handling

| Scenario                  | Behaviour                                                      |
|---------------------------|----------------------------------------------------------------|
| Empty or invalid input    | Re-prompts in menu mode; prints error + help in flag mode      |
| Unknown symbol (e.g. `SG`)| Caught before API call with format check + common symbol hints |
| API key error (-2015)     | Friendly message + hint to check credentials and IP restriction|
| Invalid symbol (-1121)    | Hint to check symbol name                                      |
| Quantity too small (-4003)| Hint to check minimum lot size                                 |
| Stop price invalid (-2021)| Hint about BUY/SELL stop price direction rules                 |
| Network failure           | Clear connection error, no crash                               |
| Unexpected error          | Full traceback written to log file only; menu continues        |

---

## Assumptions

- Uses **Binance Futures Demo Trading** (`https://demo-fapi.binance.com`) — no real funds
- Default time-in-force for LIMIT and STOP_LIMIT orders is `GTC` (Good Till Cancelled)
- Minimum quantity for BTCUSDT is `0.001` BTC — smaller values will be rejected by the API
- The bot handles order placement only — it does not track positions, calculate P&L, or manage risk
- TWAP slices are MARKET orders; total quantity is split equally across all slices

---

## Dependencies

| Package    | Version   | Purpose                    |
|------------|-----------|----------------------------|
| `requests` | >=2.31.0  | HTTP client for REST calls |

No Binance SDK is used. All HMAC-SHA256 signing and request logic is
implemented from scratch in `bot/client.py`.
