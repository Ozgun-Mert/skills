"""Current price + market data. Primary: TradingView scanner. Fallback/series: Yahoo.

Usage: python fetch_price.py --tv NASDAQ:AAPL --yahoo AAPL [--out data/AAPL/price.json]
"""
from __future__ import annotations

import argparse
import math

from common import fx_to_usd, now_iso, pct_change, tv_scan, write_json

TV_COLS = {
    "close": "price", "currency": "currency", "change": "change_1d_pct",
    "Perf.W": "perf_1w_pct", "Perf.1M": "perf_1m_pct", "Perf.3M": "perf_3m_pct",
    "Perf.YTD": "perf_ytd_pct", "Perf.Y": "perf_1y_pct",
    "price_52_week_high": "high_52w", "price_52_week_low": "low_52w",
    "volume": "volume", "average_volume_30d_calc": "avg_volume_30d",
    "market_cap_basic": "market_cap", "enterprise_value_current": "enterprise_value",
    "total_shares_outstanding": "shares_outstanding", "float_shares_outstanding": "float_shares",
    "float_shares_percent_current": "float_pct", "beta_1_year": "beta_1y",
    "RSI": "rsi_14", "SMA50": "sma50", "SMA200": "sma200", "Volatility.M": "volatility_1m_daily_pct",
    "earnings_release_next_date": "next_earnings_ts", "sector": "sector", "industry": "industry",
    "description": "name",
}


def yahoo_block(sym: str):
    import yfinance as yf
    t = yf.Ticker(sym)
    h = t.history(period="1y", auto_adjust=False)
    if h.empty:
        raise RuntimeError("empty Yahoo history")
    closes = [float(x) for x in h["Close"]]
    dates = [d.strftime("%Y-%m-%d") for d in h.index]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]

    def ann_vol(r):
        if len(r) < 5:
            return None
        m = sum(r) / len(r)
        return round(math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252) * 100, 2)

    def sma(n):
        return [None if i + 1 < n else round(sum(closes[i + 1 - n:i + 1]) / n, 4) for i in range(len(closes))]

    return {
        "last_close": closes[-1], "last_date": dates[-1],
        "realized_vol_30d_ann_pct": ann_vol(rets[-21:]),
        "realized_vol_1y_ann_pct": ann_vol(rets),
        "series": {"dates": dates, "close": [round(c, 4) for c in closes],
                   "sma50": sma(50), "sma200": sma(200)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"fetched_at": now_iso(), "tv_symbol": a.tv, "yahoo_symbol": a.yahoo, "errors": [],
           "discrepancies": [], "quote": {}, "series": None}
    tv = {}
    try:
        tv = tv_scan([a.tv], list(TV_COLS)).get(a.tv) or {}
        if not tv:
            out["errors"].append(f"TradingView returned no row for {a.tv}")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"TradingView: {e}")
    q = {v: tv.get(k) for k, v in TV_COLS.items()}
    q["source"] = {"name": "TradingView scanner", "url": f"https://www.tradingview.com/symbols/{a.tv.replace(':', '-')}/"}
    yb = None
    try:
        yb = yahoo_block(a.yahoo)
        out["series"] = yb.pop("series")
        out["series_source"] = {"name": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{a.yahoo}/history"}
        q["realized_vol_30d_ann_pct"] = yb["realized_vol_30d_ann_pct"]
        q["realized_vol_1y_ann_pct"] = yb["realized_vol_1y_ann_pct"]
        if yb["realized_vol_30d_ann_pct"] and yb["realized_vol_1y_ann_pct"]:
            q["vol_ratio_30d_vs_1y"] = round(yb["realized_vol_30d_ann_pct"] / yb["realized_vol_1y_ann_pct"], 2)
        if q.get("price") is None:  # fallback
            q["price"] = yb["last_close"]
            q["source"] = {"name": "Yahoo Finance (fallback)", "url": f"https://finance.yahoo.com/quote/{a.yahoo}"}
        else:
            diff = pct_change(yb["last_close"], q["price"])
            if diff is not None and abs(diff) > 1:
                out["discrepancies"].append({"field": "price", "tradingview": q["price"],
                                             "yahoo": yb["last_close"], "yahoo_date": yb["last_date"],
                                             "diff_pct": diff, "used": "tradingview"})
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"Yahoo: {e}")
    if q.get("price") and q.get("avg_volume_30d"):
        q["avg_dollar_volume_30d"] = round(q["price"] * q["avg_volume_30d"], 0)
    for k in ("sma50", "sma200"):
        if q.get("price") and q.get(k):
            q[f"vs_{k}_pct"] = pct_change(q["price"], q[k])
    rate, src = fx_to_usd(q.get("currency"))
    q["fx_to_usd"], q["fx_source"] = rate, src
    if rate and q.get("market_cap"):
        q["market_cap_usd"] = round(q["market_cap"] * rate, 0)
    if rate and q.get("avg_dollar_volume_30d"):
        q["avg_dollar_volume_30d_usd"] = round(q["avg_dollar_volume_30d"] * rate, 0)
    if q.get("next_earnings_ts"):
        from datetime import datetime, timezone
        q["next_earnings_date"] = datetime.fromtimestamp(q["next_earnings_ts"], timezone.utc).strftime("%Y-%m-%d")
    out["quote"] = q
    write_json(a.out, out)


if __name__ == "__main__":
    main()
