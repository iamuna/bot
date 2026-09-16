from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LIVE_URL = "https://openapi.blofin.com"
DEMO_URL = "https://demo-trading-openapi.blofin.com"


class BloFinError(RuntimeError):
    pass


class BloFinClient:
    def __init__(self, api_key: str = "", secret_key: str = "", passphrase: str = "", demo: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = DEMO_URL if demo else LIVE_URL
        self.session = requests.Session()
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=0.4,
            status_forcelist=(418, 429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=12, pool_maxsize=12))
        self.session.headers.update({"User-Agent": "Terminal3-BloFin-3m-Bot/1.0"})

    @staticmethod
    def _compact_json(body: dict[str, Any] | list[Any] | None) -> str:
        return "" if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _query(params: dict[str, Any] | None) -> str:
        if not params:
            return ""
        clean = [(k, str(v)) for k, v in params.items() if v is not None and v != ""]
        return urlencode(clean)

    def _headers(self, path_with_query: str, method: str, body_str: str) -> dict[str, str]:
        if not (self.api_key and self.secret_key and self.passphrase):
            raise BloFinError("Private endpoint requested without API credentials")
        ts = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        prehash = f"{path_with_query}{method.upper()}{ts}{nonce}{body_str}"
        hex_sig = hmac.new(self.secret_key.encode(), prehash.encode(), hashlib.sha256).hexdigest().encode()
        signature = base64.b64encode(hex_sig).decode()
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-NONCE": nonce,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None,
                 body: dict[str, Any] | list[Any] | None = None, private: bool = False) -> Any:
        query = self._query(params)
        pathq = path + ("?" + query if query else "")
        body_str = self._compact_json(body)
        headers = self._headers(pathq, method, body_str) if private else {"Content-Type": "application/json"}
        url = self.base_url + pathq
        try:
            r = self.session.request(method.upper(), url, headers=headers, data=body_str if body is not None else None, timeout=12)
        except requests.RequestException as e:
            raise BloFinError(f"Network error: {e}") from e
        try:
            payload = r.json()
        except Exception as e:
            raise BloFinError(f"Non-JSON response ({r.status_code}): {r.text[:300]}") from e
        if r.status_code >= 400:
            raise BloFinError(f"HTTP {r.status_code}: {payload}")
        code = str(payload.get("code", "0")) if isinstance(payload, dict) else "0"
        if code != "0":
            raise BloFinError(f"BloFin error {code}: {payload.get('msg', '')}")
        return payload.get("data") if isinstance(payload, dict) else payload

    def get_instrument(self, inst_id: str = "BTC-USDT") -> dict[str, Any]:
        data = self._request("GET", "/api/v1/market/instruments", {"instId": inst_id})
        if not data:
            raise BloFinError(f"Instrument not found: {inst_id}")
        return data[0]

    def get_ticker(self, inst_id: str = "BTC-USDT") -> dict[str, Any]:
        data = self._request("GET", "/api/v1/market/tickers", {"instId": inst_id})
        if not data:
            raise BloFinError(f"Ticker not found: {inst_id}")
        return data[0]

    def get_candles(self, inst_id: str = "BTC-USDT", bar: str = "3m", limit: int = 1000) -> list[dict[str, Any]]:
        limit = max(30, min(1440, int(limit)))
        data = self._request("GET", "/api/v1/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})
        out: list[dict[str, Any]] = []
        for row in data or []:
            if len(row) < 9:
                continue
            t = int(row[0])
            closed = str(row[8]) == "1"
            # qv is base-asset volume in Terminal 3.0's TA engine.
            out.append({
                "t": t,
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
                "qv": float(row[6]),
                "quote_v": float(row[7]),
                "trades": 0,
                "tb": 0.0,
                "tbq": 0.0,
                "ct": t + bar_milliseconds(bar) - 1,
                "closed": closed,
                "source": "blofin",
            })
        out.sort(key=lambda x: x["t"])
        return out

    def get_funding_rate(self, inst_id: str = "BTC-USDT") -> dict[str, Any] | None:
        data = self._request("GET", "/api/v1/market/funding-rate", {"instId": inst_id})
        if isinstance(data, list):
            return data[0] if data else None
        return data if isinstance(data, dict) else None

    def get_balance(self) -> dict[str, Any]:
        data = self._request("GET", "/api/v1/account/balance", private=True)
        return data or {}

    def get_positions(self, inst_id: str = "BTC-USDT") -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/account/positions", {"instId": inst_id}, private=True)
        return list(data or [])

    def get_positions_history(self, inst_id: str = "BTC-USDT", limit: int = 20) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/account/positions-history", {"instId": inst_id, "limit": max(1, min(100, int(limit)))}, private=True)
        return list(data or [])

    def get_margin_mode(self) -> str:
        data = self._request("GET", "/api/v1/account/margin-mode", private=True)
        return str((data or {}).get("marginMode", "cross"))

    def get_position_mode(self) -> dict[str, Any]:
        data = self._request("GET", "/api/v1/account/position-mode", private=True)
        return dict(data or {})

    def set_leverage(self, inst_id: str, leverage: float, margin_mode: str, position_side: str = "net") -> dict[str, Any]:
        body: dict[str, Any] = {
            "instId": inst_id,
            "leverage": str(int(leverage) if float(leverage).is_integer() else leverage),
            "marginMode": margin_mode,
        }
        if position_side in {"long", "short"}:
            body["positionSide"] = position_side
        data = self._request("POST", "/api/v1/account/set-leverage", body=body, private=True)
        return dict(data or {})

    def place_market_order(self, inst_id: str, margin_mode: str, position_side: str, side: str,
                           size: str, sl_price: str | None = None, tp_price: str | None = None,
                           client_order_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "instId": inst_id,
            "marginMode": margin_mode,
            "positionSide": position_side,
            "side": side,
            "orderType": "market",
            "size": size,
            "clientOrderId": client_order_id or f"t3{int(time.time()*1000)}"[-32:],
        }
        if tp_price:
            body.update({"tpTriggerPrice": tp_price, "tpOrderPrice": "-1", "tpTriggerPriceType": "mark"})
        if sl_price:
            body.update({"slTriggerPrice": sl_price, "slOrderPrice": "-1", "slTriggerPriceType": "mark"})
        data = self._request("POST", "/api/v1/trade/order", body=body, private=True)
        if isinstance(data, list) and data:
            item = data[0]
            if str(item.get("code", "0")) != "0":
                raise BloFinError(f"Order rejected: {item}")
            return item
        return dict(data or {})

    def close_position(self, inst_id: str, margin_mode: str, position_side: str, position_id: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"instId": inst_id, "marginMode": margin_mode, "positionSide": position_side}
        if position_id:
            body["positionId"] = position_id
        data = self._request("POST", "/api/v1/trade/close-position", body=body, private=True)
        return dict(data or {})


def bar_milliseconds(bar: str) -> int:
    n = int(bar[:-1])
    unit = bar[-1]
    if unit == "m":
        return n * 60_000
    if unit == "H":
        return n * 3_600_000
    if unit == "D":
        return n * 86_400_000
    if unit == "W":
        return n * 604_800_000
    if unit == "M":
        return n * 30 * 86_400_000
    raise ValueError(f"Unsupported bar: {bar}")


def quantize_step(value: float, step: float, rounding=ROUND_DOWN) -> str:
    d = Decimal(str(value))
    s = Decimal(str(step))
    if s <= 0:
        return format(d, "f")
    q = (d / s).to_integral_value(rounding=rounding) * s
    decimals = max(0, -s.as_tuple().exponent)
    return f"{q:.{decimals}f}"


def quantize_price(value: float, tick: float) -> str:
    return quantize_step(value, tick, ROUND_HALF_UP)
