# Binance Futures Testnet Trading Bot

A clean, production-structured Python CLI app for placing orders on the
**Binance USDT-M Futures Testnet**. Uses direct REST calls — no third-party
Binance SDK required.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Low-level REST client (auth, signing, HTTP)
│   ├── orders.py            # Order placement logic (MARKET, LIMIT, STOP_MARKET)
│   ├── validators.py        # Input validation functions
│   └── logging_config.py   # Rotating file + console log setup
├── cli.py                   # CLI entry point (argparse + interactive mode)
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

### 3. Get Testnet API credentials

1. Visit **https://testnet.binancefuture.com**
2. Log in (or register — it's free, no real money)
3. Go to **API Management** (top-right menu)
4. Click **Generate** to create a key pair
5. Copy **both** the API Key and Secret (secret shown only once!)

### 4. Set your credentials

**Option A — Edit `cli.py` directly (simplest):**

Open `cli.py` and replace these two lines near the top:

```python
API_KEY    = "PASTE_YOUR_API_KEY_HERE"
API_SECRET = "PASTE_YOUR_API_SECRET_HERE"
```

**Option B — Environment variables (recommended for security):**

```bash
# Windows CMD
set BINANCE_TESTNET_API_KEY=your_actual_key
set BINANCE_TESTNET_API_SECRET=your_actual_secret

# PowerShell
$env:BINANCE_TESTNET_API_KEY = "your_actual_key"
$env:BINANCE_TESTNET_API_SECRET = "your_actual_secret"

# Linux / macOS
export BINANCE_TESTNET_API_KEY=your_actual_key
export BINANCE_TESTNET_API_SECRET=your_actual_secret
```

---

## How to Run

All commands are run from the `trading_bot/` directory.

### Check account balance

```bash
python cli.py --balance
```

### Place a Market BUY order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Place a Limit SELL order

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 80000
```

### Place a Stop-Market order (bonus order type)

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 70000
```

### Interactive mode (prompts for every field)

```bash
python cli.py --interactive
```

Or just run with no arguments:

```bash
python cli.py
```

### Full help

```bash
python cli.py --help
```

---

## Example Output

```
── Order Request ───────────────────────────────
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Quantity    : 0.001
────────────────────────────────────────────────

──────────────────────────────────────────────────
  ORDER PLACED SUCCESSFULLY
──────────────────────────────────────────────────
  Order ID    : 4062615537
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Qty         : 0.001
  Executed Qty: 0.001
  Avg Price   : 76291.40
  Status      : FILLED
──────────────────────────────────────────────────
```

---

## Logging

Logs are written to `logs/trading_bot.log` automatically.

- **Console** shows INFO-level and above (concise)
- **File** captures DEBUG-level (full request/response trace)

The log file rotates at 5 MB and keeps 3 backups.

Sample log entries are included in `logs/trading_bot.log`.

---

## Supported Order Types

| Type          | Required fields                    | Notes                          |
|---------------|------------------------------------|--------------------------------|
| `MARKET`      | symbol, side, quantity             | Fills immediately at best price|
| `LIMIT`       | symbol, side, quantity, price      | Rests in order book (GTC/IOC)  |
| `STOP_MARKET` | symbol, side, quantity, price      | `--price` = stop trigger price |

---

## Error Handling

| Scenario            | Behaviour                                         |
|---------------------|---------------------------------------------------|
| Invalid CLI input   | Validation error printed, help shown, exit 1      |
| API key error -2015 | Error + hint to check credentials                 |
| Invalid symbol      | Error + hint to check symbol name                 |
| Network failure     | Clear connection error message, exit 1            |
| Unexpected error    | Full traceback written to log file only           |

---

## Assumptions

- Testnet only — no real funds are used or needed
- Default time-in-force for LIMIT orders is `GTC` (Good Till Cancelled)
- Quantity precision must match the symbol's lot size filter (BTCUSDT = 0.001 minimum)
- The bot does not manage positions or calculate P&L — order placement only

---

## Dependencies

| Package    | Purpose                   |
|------------|---------------------------|
| `requests` | HTTP client for REST calls |

No Binance SDK is used — all signing and request logic is implemented from scratch.
