"""
client.py
---------
Low-level Binance Futures Testnet REST client.
Handles authentication (HMAC-SHA256), request dispatch,
response parsing, and error propagation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests

log = logging.getLogger("trading_bot.client")

BASE_URL = "https://demo-fapi.binance.com"


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error payload."""

    def __init__(self, code: int, message: str):
        self.code    = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceFuturesClient:
    """
    Thin wrapper around Binance USDT-M Futures Testnet REST API.

    Parameters
    ----------
    api_key    : Testnet API key
    api_secret : Testnet API secret
    base_url   : Override for testing / different environments
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = BASE_URL):
        self.api_key    = api_key
        self._secret    = api_secret.encode()
        self.base_url   = base_url.rstrip("/")
        self._session   = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        payload   = urlencode(params)
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> Any:
        params = params or {}
        if signed:
            params = self._sign(params)

        url = self.base_url + path
        log.debug("→ %s %s  params=%s", method.upper(), url, params)

        try:
            if method.upper() in ("GET", "DELETE"):
                resp = self._session.request(method, url, params=params, timeout=10)
            else:
                resp = self._session.request(method, url, data=params, timeout=10)
        except requests.exceptions.ConnectionError as exc:
            log.error("Network error: %s", exc)
            raise ConnectionError(f"Cannot reach {self.base_url}. Check your internet connection.") from exc
        except requests.exceptions.Timeout:
            log.error("Request timed out: %s %s", method, url)
            raise TimeoutError("Request timed out after 10 seconds.") from None

        return self._handle_response(resp)

    @staticmethod
    def _handle_response(resp: requests.Response) -> Any:
        log.debug("← HTTP %s  body=%s", resp.status_code, resp.text[:500])
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            return {}

        if not resp.ok:
            code = data.get("code", resp.status_code)
            msg  = data.get("msg",  resp.text)
            log.error("API error %s: %s", code, msg)
            raise BinanceAPIError(code, msg)

        return data

    # ──────────────────────────────────────────────────────────────────────
    # Public endpoints (no auth)
    # ──────────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        self._request("GET", "/fapi/v1/ping")
        log.debug("Ping OK")
        return True

    def server_time(self) -> int:
        return self._request("GET", "/fapi/v1/time")["serverTime"]

    def get_price(self, symbol: str) -> float:
        data = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(data["price"])

    # ──────────────────────────────────────────────────────────────────────
    # Private / signed endpoints
    # ──────────────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_balance(self, asset: str = "USDT") -> float:
        account = self.get_account()
        for b in account.get("assets", []):
            if b["asset"] == asset.upper():
                return float(b["availableBalance"])
        return 0.0

    def get_open_orders(self, symbol: str | None = None) -> list:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params, signed=True)

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        return self._request(
            "POST", "/fapi/v1/leverage",
            {"symbol": symbol, "leverage": leverage},
            signed=True,
        )

    def place_order(self, **kwargs) -> dict:
        """
        Place a futures order. All parameters passed as keyword args
        are forwarded directly to the API.
        """
        return self._request("POST", "/fapi/v1/order", kwargs, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        return self._request(
            "DELETE", "/fapi/v1/order",
            {"symbol": symbol, "orderId": order_id},
            signed=True,
        )
