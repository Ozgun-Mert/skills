"""Shared helpers for stock-analyzer data scripts.

Every script writes JSON with `fetched_at`, per-block `source`, and `errors[]`.
Never fabricate: failed fields stay null and are recorded in errors.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing package 'requests'. Run: python -m pip install -r requirements.txt")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
# SEC requires a descriptive User-Agent with contact info.
SEC_UA = os.environ.get("SEC_USER_AGENT", "stock-analyzer research stock-analyzer@example.com")
TIMEOUT = 20

TV_SCAN_URL = "https://scanner.tradingview.com/global/scan"
TV_SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

# TradingView exchange -> Yahoo suffix (Euronext depends on country).
YAHOO_SUFFIX = {
    "NASDAQ": "", "NYSE": "", "AMEX": "", "NYSE ARCA": "", "CBOE": "", "OTC": "",
    "BIST": ".IS", "XETR": ".DE", "FWB": ".F", "LSE": ".L", "TSE": ".T", "HKEX": ".HK",
    "SIX": ".SW", "TSX": ".TO", "TSXV": ".V", "ASX": ".AX", "KRX": ".KS", "NSE": ".NS",
    "BSE": ".BO", "MIL": ".MI", "BME": ".MC", "OMXSTO": ".ST", "OMXCOP": ".CO",
    "OMXHEX": ".HE", "OSL": ".OL", "TWSE": ".TW", "SSE": ".SS", "SZSE": ".SZ",
    "BMFBOVESPA": ".SA", "JSE": ".JO", "TADAWUL": ".SR", "SGX": ".SI", "VIE": ".VI",
    "SET": ".BK", "MYX": ".KL", "IDX": ".JK", "BMV": ".MX", "TASE": ".TA", "NZX": ".NZ", "GPW": ".WA",
    "BET": ".BD", "ATHEX": ".AT", "PSE": ".PS", "KOSDAQ": ".KQ",
}
EURONEXT_SUFFIX = {"NL": ".AS", "FR": ".PA", "BE": ".BR", "PT": ".LS", "IE": ".IR"}
# Yahoo exchange code -> TradingView exchange (fallback path).
YAHOO_EXCH_TO_TV = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE", "ASE": "AMEX",
    "IST": "BIST", "AMS": "EURONEXT", "PAR": "EURONEXT", "BRU": "EURONEXT", "LIS": "EURONEXT",
    "GER": "XETR", "FRA": "FWB", "LSE": "LSE", "JPX": "TSE", "HKG": "HKEX", "EBS": "SIX",
    "TOR": "TSX", "ASX": "ASX", "KSC": "KRX", "NSI": "NSE", "BSE": "BSE", "MIL": "MIL",
    "MCE": "BME", "STO": "OMXSTO", "CPH": "OMXCOP", "OSL": "OSL", "TAI": "TWSE",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http(method: str, url: str, *, retries: int = 3, sec: bool = False, **kw):
    headers = kw.pop("headers", {})
    headers.setdefault("User-Agent", SEC_UA if sec else UA)
    kw.setdefault("timeout", TIMEOUT)
    last = None
    for i in range(retries):
        try:
            r = requests.request(method, url, headers=headers, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (2 ** i))
    raise RuntimeError(f"{method} {url} failed after {retries} tries: {last}")


def tv_scan(symbols: list[str], columns: list[str]) -> dict[str, dict]:
    """TradingView scanner (unofficial). Returns {tv_symbol: {column: value}}."""
    # GOTCHA: the global scanner silently converts snapshot fundamentals (market cap,
    # EV, TTM, price targets) to USD while *_fy_h history and `close` stay native.
    # price_conversion.to_symbol forces everything into the symbol's trading currency.
    r = http("POST", TV_SCAN_URL, json={"symbols": {"tickers": symbols}, "columns": columns,
                                        "price_conversion": {"to_symbol": True}})
    out = {}
    for row in r.json().get("data", []):
        out[row["s"]] = dict(zip(columns, row["d"]))
    return out


def yahoo_symbol_for(exchange: str, ticker: str, country: str | None) -> str:
    if exchange == "EURONEXT":
        return ticker + EURONEXT_SUFFIX.get((country or "").upper(), ".PA")
    suffix = YAHOO_SUFFIX.get(exchange)
    if suffix is None:
        return ticker
    t = ticker.replace(".", "-") if suffix == "" else ticker
    return t + suffix


def fx_to_usd(currency: str | None) -> tuple[float | None, str]:
    """Units of USD per 1 unit of `currency`. Returns (rate, source)."""
    if not currency or currency.upper() == "USD":
        return 1.0, "identity"
    cur = currency.upper()
    try:
        d = tv_scan([f"FX_IDC:{cur}USD"], ["close"])
        v = next(iter(d.values()), {}).get("close")
        if v:
            return float(v), f"TradingView FX_IDC:{cur}USD"
    except Exception:  # noqa: BLE001
        pass
    try:
        import yfinance as yf
        h = yf.Ticker(f"{cur}USD=X").history(period="5d")
        if not h.empty:
            return float(h["Close"].iloc[-1]), f"Yahoo {cur}USD=X"
    except Exception:  # noqa: BLE001
        pass
    return None, "unavailable"


def clean(v):
    """Make values JSON-safe (NaN/inf -> None, numpy -> python)."""
    if v is None:
        return None
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    return v


def pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new - old) / abs(old) * 100, 2)


def cagr(last, first, years):
    if last is None or first is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return round(((last / first) ** (1 / years) - 1) * 100, 2)


def write_json(path: str | None, data: dict) -> None:
    data = clean(data)
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    # Always echo a compact status line, full JSON only when no --out given.
    if path:
        errs = len(data.get("errors", []))
        print(f"wrote {path} ({errs} errors)")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def split_symbol(sym: str) -> tuple[str | None, str]:
    """'NASDAQ:AAPL' -> ('NASDAQ','AAPL'); 'AAPL' -> (None,'AAPL')."""
    if ":" in sym:
        ex, t = sym.split(":", 1)
        return ex.upper(), t.upper()
    return None, sym.upper()
