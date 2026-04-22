# Binance Futures Testnet Trading Bot

A clean, production-structured Python CLI app for placing orders on the
**Binance USDT-M Futures Testnet** (`https://testnet.binancefuture.com`).
Uses direct REST calls — no third-party Binance SDK required.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Low-level REST client (HMAC auth, signing, HTTP)
│   ├── orders.py            # Order placement logic (all 5 order types)
│   ├── validators.py        # Input validation with clear error messages
│   └── logging_config.py   # Rotating file + console log setup
├── cli.py                   # CLI entry point (flag mode + interactive menu)
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

Only one external dependency: `requests`.

### 3. Get Testnet API credentials

1. Visit **https://testnet.binancefuture.com**
2. Log in with your GitHub account (click **Login with GitHub**)
3. Click your username (top right) → **API Management**
4. Click **Generate** to create a fresh key pair
5. Copy **both** the API Key and Secret — the secret is shown **only once**

> **Note on endpoints:** The task specifies `https://testnet.binancefuture.com`
> as the base URL. If you cannot access this testnet (it uses GitHub login and
> may redirect in some regions), you can switch to Binance Demo Trading by
> changing `BASE_URL` in `bot/client.py` to `https://demo-fapi.binance.com`
> and using keys from your Binance account's API Management page instead.
> The API paths and authentication are identical — only the base URL differs.

### 4. Set your credentials

Open `cli.py` and replace the two placeholder lines:

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

All commands are run from the project root (`trading_bot/` directory).

### Interactive menu (recommended)

```bash
python cli.py --menu
```

Launches a guided step-by-step menu. Validates every input and re-prompts
on errors. Loops back to the main menu after each action. Exits only when
you select "Exit".

Running with no arguments also launches the menu:

```bash
python cli.py
```

---

### Direct flag mode

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

#### Stop-Limit SELL *(Bonus order type)*

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \
  --quantity 0.001 --price 75000 --limit-price 74900
```

`--price` = stop trigger price, `--limit-price` = limit fill price after trigger.

#### TWAP BUY *(Bonus order type)*

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
14:40:05  [INFO    ]  Placing MARKET BUY order | symbol=BTCUSDT qty=0.001
----------------------------------------------------
  ORDER PLACED SUCCESSFULLY
----------------------------------------------------
  Order ID    : 13057093602
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Qty         : 0.0010
  Executed Qty: 0.0010
  Avg Price   : 78291.40
  Status      : FILLED
----------------------------------------------------
```

**TWAP order:**

```
  [TWAP] Starting: 5 slices of 0.001 BTC every 10s
  [TWAP] Total: 0.005 | Side: BUY
  Slice    Status       Avg Price      Qty
  ------------------------------------------------
  1/5      NEW          78291.40       0.001
  [TWAP] Waiting 10s ...
  2/5      NEW          78305.20       0.001
  ...
  [TWAP] Done. 5/5 slices filled.
```

---

## Supported Order Types

| Type          | Required flags                                      | Description                                          |
|---------------|-----------------------------------------------------|------------------------------------------------------|
| `MARKET`      | `--symbol --side --quantity`                        | Fills immediately at best available price            |
| `LIMIT`       | `--symbol --side --quantity --price`                | Rests in order book until filled or cancelled        |
| `STOP_MARKET` | `--symbol --side --quantity --price`                | `--price` = stop trigger; fills at market on trigger |
| `STOP_LIMIT`  | `--symbol --side --quantity --price --limit-price`  | Trigger + controlled fill price *(Bonus)*            |
| `TWAP`        | `--symbol --side --quantity --slices --interval`    | Equal timed slices to reduce market impact *(Bonus)* |

---

## All CLI Flags

| Flag             | Type    | Description                                                    |
|------------------|---------|----------------------------------------------------------------|
| `--symbol`       | string  | Trading pair, e.g. `BTCUSDT`                                   |
| `--side`         | string  | `BUY` or `SELL`                                                |
| `--type`         | string  | Order type (see table above)                                   |
| `--quantity`     | float   | Contract quantity (BTCUSDT minimum: 0.001)                     |
| `--price`        | float   | Limit price (LIMIT) or stop trigger price (STOP orders)        |
| `--limit-price`  | float   | Limit fill price for `STOP_LIMIT` orders                       |
| `--tif`          | string  | Time-in-force: `GTC` (default), `IOC`, `FOK`                  |
| `--slices`       | int     | TWAP: slices count, 2–20 (default `5`)                         |
| `--interval`     | int     | TWAP: seconds between slices, 5–300 (default `10`)             |
| `--balance`      | flag    | Show USDT balance and BTCUSDT price, then exit                 |
| `--menu`         | flag    | Launch the interactive guided menu                             |

---

## Logging

Logs are written automatically to `logs/trading_bot.log`.

| Handler | Level | Content |
|---------|-------|---------|
| Console | INFO  | Order actions, confirmations, errors |
| File    | DEBUG | Full API request params, response bodies, timestamps |

The log file rotates at 5 MB and keeps 3 backups.

Sample log entries:
```
2026-04-21 14:40:05  [INFO    ]  trading_bot.orders  Placing MARKET BUY order | symbol=BTCUSDT qty=0.001
2026-04-21 14:40:05  [DEBUG   ]  trading_bot.client  REQUEST  POST https://testnet.binancefuture.com/fapi/v1/order
2026-04-21 14:40:06  [DEBUG   ]  trading_bot.client  RESPONSE HTTP 200  body={"orderId":13057093602,...}
2026-04-21 14:40:06  [INFO    ]  trading_bot.orders  MARKET order accepted | orderId=13057093602 status=FILLED
2026-04-21 14:40:06  [INFO    ]  trading_bot         Order completed | orderId=13057093602 status=FILLED
```

---

## Error Handling

| Scenario                   | Behaviour                                                        |
|----------------------------|------------------------------------------------------------------|
| Empty or invalid input     | Re-prompts in menu; prints error + `--help` in flag mode         |
| Symbol too short / wrong   | Caught before API call; shows common symbol suggestions          |
| Missing required price     | Clear message specifying which flag to use                       |
| API key error (-2015)      | Friendly message + hint to check credentials and IP restriction  |
| Invalid symbol (-1121)     | Hint to use a valid pair like BTCUSDT                            |
| Quantity too small (-4003) | Hint about minimum lot size                                      |
| Stop price wrong (-2021)   | Hint about BUY/SELL stop price direction rules                   |
| Network failure            | Clear message, no crash; menu continues                          |
| Request timeout            | Clear message after 10 seconds                                   |
| Unexpected error           | Full traceback in log file; brief message in terminal            |

---

## Assumptions

- Uses the Binance Futures Testnet (`https://testnet.binancefuture.com`) — no real funds involved
- Default time-in-force for LIMIT and STOP_LIMIT orders is `GTC` (Good Till Cancelled)
- Minimum quantity for BTCUSDT is `0.001` — smaller values will be rejected by the API
- Bot handles order placement only — no position tracking, P&L calculation, or risk management
- TWAP slices are MARKET orders; total quantity is divided equally across all slices

---

## Dependencies

| Package    | Version   | Purpose                                     |
|------------|-----------|---------------------------------------------|
| `requests` | >=2.31.0  | HTTP client for all REST API calls          |

No Binance SDK is used. HMAC-SHA256 signing, request dispatch, and
response parsing are all implemented from scratch in `bot/client.py`.
