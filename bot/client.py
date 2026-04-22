"""
bot/client.py
=============
Low-level REST client for the Binance USDT-M Futures Testnet.

Responsibilities:
  - HMAC-SHA256 request signing
  - HTTP request dispatch (GET / POST / DELETE)
  - Response parsing and error propagation
  - Network-level exception handling

NOTE ON ENDPOINT
----------------
The task specifies https://testnet.binancefuture.com as the base URL.
This is the correct endpoint for the Binance Futures Testnet.

If you are using Binance Demo Trading (accessed via your main Binance
account), change BASE_URL to:  https://demo-fapi.binance.com
Both endpoints use identical API paths and authentication — only the
URL differs.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests

# Module-level logger — inherits from root "trading_bot" logger
log = logging.getLogger("trading_bot.client")

# ── Base URL ──────────────────────────────────────────────────────────────────
# Task-specified testnet endpoint. Change to https://demo-fapi.binance.com
# if you are using Binance Demo Trading instead of the Futures Testnet.
BASE_URL = "https://testnet.binancefuture.com"


# ── Custom exception ──────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """
    Raised when the Binance API returns an error payload.

    Attributes
    ----------
    code    : Binance error code (negative integer, e.g. -1121)
    message : Human-readable error description from the API
    """

    def __init__(self, code: int, message: str):
        self.code    = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


# ── Client class ──────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API.

    Handles signing, session management, and response validation.
    All business logic lives in orders.py — this layer only speaks HTTP.

    Parameters
    ----------
    api_key    : Testnet API key (from API Management on the testnet site)
    api_secret : Testnet API secret (shown only once at creation)
    base_url   : API base URL; defaults to the task-specified testnet URL
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = BASE_URL):
        self.api_key  = api_key
        self._secret  = api_secret.encode()          # encode once for reuse
        self.base_url = base_url.rstrip("/")

        # Persistent session — reuses TCP connections across requests
        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

    # ── Private helpers ───────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        """
        Append a timestamp and HMAC-SHA256 signature to the parameter dict.

        Binance requires all signed requests to include:
          - timestamp : current time in milliseconds
          - signature : HMAC-SHA256 of the full query string using the secret key
        """
        params["timestamp"] = int(time.time() * 1000)
        query_string        = urlencode(params)
        signature           = hmac.new(
            self._secret, query_string.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> Any:
        """
        Dispatch an HTTP request to the Binance API.

        Parameters
        ----------
        method : HTTP verb — "GET", "POST", or "DELETE"
        path   : API path, e.g. "/fapi/v1/order"
        params : Query/body parameters as a plain dict
        signed : If True, appends timestamp + signature before sending

        Raises
        ------
        ConnectionError : If the server cannot be reached
        TimeoutError    : If the request takes longer than 10 seconds
        BinanceAPIError : If the API returns a non-2xx response
        """
        params = params or {}
        if signed:
            params = self._sign(params)

        url = self.base_url + path
        log.debug("REQUEST  %s %s  params=%s", method.upper(), url, params)

        try:
            # GET and DELETE use query string; POST sends body
            if method.upper() in ("GET", "DELETE"):
                resp = self._session.request(method, url, params=params, timeout=10)
            else:
                resp = self._session.request(method, url, data=params, timeout=10)

        except requests.exceptions.ConnectionError as exc:
            log.error("Network error reaching %s: %s", self.base_url, exc)
            raise ConnectionError(
                f"Cannot reach {self.base_url}. Check your internet connection."
            ) from exc

        except requests.exceptions.Timeout:
            log.error("Request timed out: %s %s", method, url)
            raise TimeoutError("Request timed out after 10 seconds.") from None

        return self._handle_response(resp)

    @staticmethod
    def _handle_response(resp: requests.Response) -> Any:
        """
        Parse the API response and raise BinanceAPIError on failure.

        Binance always returns JSON. Non-2xx responses include a
        'code' (negative int) and 'msg' (error description).
        """
        log.debug("RESPONSE HTTP %s  body=%s", resp.status_code, resp.text[:500])

        try:
            data = resp.json()
        except ValueError:
            # Non-JSON response — raise HTTP error directly
            resp.raise_for_status()
            return {}

        if not resp.ok:
            code = data.get("code", resp.status_code)
            msg  = data.get("msg",  resp.text)
            log.error("API error %s: %s", code, msg)
            raise BinanceAPIError(code, msg)

        return data

    # ── Public endpoints (no authentication required) ─────────────────────────

    def ping(self) -> bool:
        """Check connectivity to the API server. Returns True on success."""
        self._request("GET", "/fapi/v1/ping")
        log.debug("Ping OK")
        return True

    def server_time(self) -> int:
        """Return the server's current time in milliseconds."""
        return self._request("GET", "/fapi/v1/time")["serverTime"]

    def get_price(self, symbol: str) -> float:
        """Return the latest mark price for the given symbol."""
        data = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(data["price"])

    # ── Private endpoints (HMAC signature required) ───────────────────────────

    def get_account(self) -> dict:
        """Return full account info including balances and positions."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_balance(self, asset: str = "USDT") -> float:
        """
        Return the available balance for a specific asset.

        Parameters
        ----------
        asset : Asset ticker, e.g. "USDT", "BTC" (default: "USDT")
        """
        account = self.get_account()
        for b in account.get("assets", []):
            if b["asset"] == asset.upper():
                return float(b["availableBalance"])
        return 0.0

    def get_open_orders(self, symbol: str | None = None) -> list:
        """
        Return all open orders. Optionally filter by symbol.

        Parameters
        ----------
        symbol : e.g. "BTCUSDT". If None, returns orders for all symbols.
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params, signed=True)

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """
        Set leverage for a symbol.

        Parameters
        ----------
        symbol   : Trading pair, e.g. "BTCUSDT"
        leverage : Leverage multiplier, 1–125
        """
        return self._request(
            "POST", "/fapi/v1/leverage",
            {"symbol": symbol, "leverage": leverage},
            signed=True,
        )

    def place_order(self, **kwargs) -> dict:
        """
        Place a futures order.

        All keyword arguments are forwarded directly to the API.
        Required fields vary by order type — see orders.py for typed wrappers.

        Common fields:
          symbol      : Trading pair, e.g. "BTCUSDT"
          side        : "BUY" or "SELL"
          type        : "MARKET", "LIMIT", "STOP_MARKET", "STOP"
          quantity    : Contract quantity
          price       : Required for LIMIT and STOP orders
          stopPrice   : Required for STOP_MARKET and STOP orders
          timeInForce : "GTC", "IOC", or "FOK" (required for LIMIT/STOP)
        """
        return self._request("POST", "/fapi/v1/order", kwargs, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """
        Cancel an open order by its order ID.

        Parameters
        ----------
        symbol   : Trading pair the order belongs to
        order_id : Binance-assigned order ID
        """
        return self._request(
            "DELETE", "/fapi/v1/order",
            {"symbol": symbol, "orderId": order_id},
            signed=True,
        )
