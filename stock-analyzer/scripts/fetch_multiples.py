"""Valuation multiples (current + 5y history) and analyst consensus.

Usage: python fetch_multiples.py --tv NASDAQ:AAPL --yahoo AAPL --fin data/AAPL/financials.json [--out ...]

Current multiples + consensus: TradingView. History: fiscal-year-end price (Yahoo)
divided by per-year fundamentals from financials.json (run fetch_financials first).
Historical EV/EBITDA is approximate (implied shares = NI/EPS; EV = mcap + debt - cash).
"""
from __future__ import annotations

import argparse
import statistics
from datetime import datetime, timezone

from common import load_json, now_iso, tv_scan, write_json

TV = {
    "price_earnings_ttm": "pe_ttm", "price_earnings_fwd": "pe_fwd",
    "price_earnings_growth_ttm": "peg", "enterprise_value_ebitda_ttm": "ev_ebitda",
    "price_sales_current": "ps", "price_book_fq": "pb", "price_free_cash_flow_ttm": "p_fcf",
    "dividends_yield_current": "dividend_yield_pct", "enterprise_value_current": "ev",
    "total_revenue_ttm": "_rev_ttm", "market_cap_basic": "market_cap", "close": "_price",
    "price_target_low": "target_low", "price_target_average": "target_mean", "price_target_high": "target_high",
    "recommendation_buy": "rating_buy", "recommendation_over": "rating_overweight",
    "recommendation_hold": "rating_hold", "recommendation_under": "rating_underweight",
    "recommendation_sell": "rating_sell", "recommendation_total": "rating_total",
    "recommendation_mark": "rating_mark_1buy_5sell", "earnings_per_share_forecast_next_fy": "eps_fwd_next_fy",
    "revenue_forecast_next_fy": "revenue_fwd_next_fy",
}


def fy_end_prices(sym: str, years: list[int]) -> dict[int, float]:
    import yfinance as yf
    t = yf.Ticker(sym)
    try:
        ts = t.info.get("lastFiscalYearEnd")
        fy_end = datetime.fromtimestamp(ts, timezone.utc) if ts else None
    except Exception:  # noqa: BLE001
        fy_end = None
    h = t.history(period="7y", interval="1d", auto_adjust=False)
    out = {}
    for y in years:
        # fiscal year label = calendar year of FY end (matches fetch_financials)
        m, d = (fy_end.month, fy_end.day) if fy_end else (12, 31)
        try:
            target = datetime(y, m, min(d, 28))
        except ValueError:
            continue
        sub = h[h.index.tz_localize(None) <= target] if h.index.tz is not None else h[h.index <= target]
        if not sub.empty and (target - sub.index[-1].to_pydatetime().replace(tzinfo=None)).days < 10:
            out[y] = float(sub["Close"].iloc[-1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--fin", help="financials.json from fetch_financials.py")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"fetched_at": now_iso(), "tv_symbol": a.tv, "errors": [],
           "source": {"name": "TradingView scanner", "url": f"https://www.tradingview.com/symbols/{a.tv.replace(':', '-')}/"}}
    cur = {}
    try:
        raw = tv_scan([a.tv], list(TV)).get(a.tv) or {}
        cur = {v: raw.get(k) for k, v in TV.items()}
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"TradingView: {e}")
    if cur.get("ev") and cur.get("_rev_ttm"):
        cur["ev_sales"] = round(cur["ev"] / cur["_rev_ttm"], 2)
    if cur.get("p_fcf"):
        cur["fcf_yield_pct"] = round(100 / cur["p_fcf"], 2)
    if cur.get("_price") and cur.get("target_mean"):
        cur["target_upside_pct"] = round((cur["target_mean"] / cur["_price"] - 1) * 100, 2)
    out["current"] = {k: v for k, v in cur.items() if not k.startswith("_")}

    hist = []
    if a.fin:
        try:
            fin = load_json(a.fin)
            years = [r["fy"] for r in fin.get("annual", [])]
            prices = fy_end_prices(a.yahoo, years)
            for r in fin.get("annual", []):
                p = prices.get(r["fy"])
                row = {"fy": r["fy"], "fy_end_price": p, "pe": None, "ev_ebitda": None, "ps": None}
                if p and r.get("eps_diluted"):
                    row["pe"] = round(p / r["eps_diluted"], 2) if r["eps_diluted"] > 0 else None
                    shares = r["net_income"] / r["eps_diluted"] if r.get("net_income") and r["eps_diluted"] else None
                    if shares and shares > 0:
                        mcap = p * shares
                        if r.get("revenue"):
                            row["ps"] = round(mcap / r["revenue"], 2)
                        if r.get("ebitda") and r["ebitda"] > 0:
                            ev = mcap + (r.get("total_debt") or 0) - (r.get("cash") or 0)
                            row["ev_ebitda"] = round(ev / r["ebitda"], 2)
                hist.append(row)
            out["history_source"] = {"name": "Yahoo FY-end close / financials.json", "approx": ["ev_ebitda", "ps"]}
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"history: {e}")
    out["history"] = hist
    avg = {}
    for k in ("pe", "ev_ebitda", "ps"):
        vals = [h[k] for h in hist if h.get(k) is not None and h[k] > 0]
        avg[k] = round(statistics.mean(vals), 2) if vals else None
        avg[f"{k}_n_years"] = len(vals)
    out["avg_5y"] = avg
    write_json(a.out, out)


if __name__ == "__main__":
    main()
