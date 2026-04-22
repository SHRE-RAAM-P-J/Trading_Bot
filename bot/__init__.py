"""
bot package
===========
Binance Futures Testnet Trading Bot — core library.

Package layout
--------------
  client.py        : Low-level REST client (signing, HTTP, error handling)
  orders.py        : Order placement logic (MARKET, LIMIT, STOP_MARKET, STOP_LIMIT, TWAP)
  validators.py    : Input validation — called before any API request is made
  logging_config.py: Dual console + rotating file log setup

Public API
----------
Import the most commonly used symbols directly from the package:

  from bot import BinanceFuturesClient, BinanceAPIError
  from bot import place_market_order, place_limit_order
  from bot import setup_logging
"""

from .logging_config import setup_logging
from .client import BinanceFuturesClient, BinanceAPIError
from .orders import (
    place_market_order,
    place_limit_order,
    place_stop_market_order,
    place_stop_limit_order,
    place_twap_order,
    print_order_result,
)
from .validators import (
    validate_symbol,
    validate_symbol_live,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_limit_price,
    validate_twap_slices,
    validate_twap_interval,
)
