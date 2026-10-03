"""Peer comparison table (USD-normalized) + peer medians.

Usage:
  python fetch_peers.py --subject NASDAQ:GOOGL --peers "META, AMZN, MSFT, TSLA, BIDU" \
      [--segments '{"Ads":["META","AMZN"],"Cloud":["AMZN","MSFT"]}'] [--out ...]

Peers may be tickers, names or TV symbols. Choose peers PER BUSINESS SEGMENT.
"""
from __future__ import annotations

import argparse
import json
import statistics

from common import fx_to_usd, now_iso, tv_scan, write_json
from resolve_ticker import resolve_one

COLS = ["description", "close", "currency", "market_cap_basic", "total_revenue_ttm", "gross_profit_ttm",
        "oper_income_ttm", "net_income_ttm", "free_cash_flow_ttm", "research_and_dev_ratio_ttm",
        "price_earnings_ttm", "enterprise_value_ebitda_ttm", "price_sales_current", "total_revenue_fy_h",
        "net_income_fy_h", "Perf.Y", "sector", "industry", "country"]


def to_tv(sym: str) -> str | None:
    if ":" in sym:
        return sym.upper()
    r = resolve_one(sym)
    return r.get("tv_symbol") if r.get("supported") else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, help="TV symbol of the analyzed stock")
    ap.add_argument("--peers", required=True)
    ap.add_argument("--segments", help='JSON {"segment": [peer, ...]} for per-segment grouping')
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"fetched_at": now_iso(), "subject": a.subject, "errors": [],
           "source": {"name": "TradingView scanner (TTM, native -> USD)", "url": "https://www.tradingview.com/"}}
    raw_peers = [p.strip() for p in a.peers.split(",") if p.strip()]
    mapping = {}
    for p in raw_peers:
        tv = to_tv(p)
        if tv:
            mapping[p] = tv
        else:
            out["errors"].append(f"could not resolve peer '{p}'")
    symbols = [a.subject] + [s for s in dict.fromkeys(mapping.values()) if s != a.subject]
    try:
        data = tv_scan(symbols, COLS)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"TradingView: {e}")
        data = {}
    fx_cache: dict = {}
    rows = []
    for s in symbols:
        d = data.get(s)
        if not d:
            out["errors"].append(f"no data for {s}")
            continue
        cur = d.get("currency")
        if cur not in fx_cache:
            fx_cache[cur] = fx_to_usd(cur)
        rate = fx_cache[cur][0]

        def usd(v):
            return round(v * rate, 0) if v is not None and rate else None
        rev = d.get("total_revenue_ttm")
        hist = d.get("total_revenue_fy_h") or []
        nih = d.get("net_income_fy_h") or []

        def margin(x):
            return round(x / rev * 100, 2) if x is not None and rev else None
        rows.append({
            "tv_symbol": s, "ticker": s.split(":")[1], "name": d.get("description"), "is_subject": s == a.subject,
            "country": d.get("country"), "currency": cur, "fx_to_usd": rate,
            "market_cap_usd": usd(d.get("market_cap_basic")), "revenue_ttm_usd": usd(rev),
            "rev_growth_last_fy_pct": round((hist[0] / hist[1] - 1) * 100, 2) if len(hist) > 1 and hist[1] else None,
            "ni_growth_last_fy_pct": round((nih[0] / nih[1] - 1) * 100, 2) if len(nih) > 1 and nih[1] and nih[1] > 0 else None,
            "gross_margin_pct": margin(d.get("gross_profit_ttm")), "op_margin_pct": margin(d.get("oper_income_ttm")),
            "net_margin_pct": margin(d.get("net_income_ttm")), "rnd_pct": d.get("research_and_dev_ratio_ttm"),
            "fcf_ttm_usd": usd(d.get("free_cash_flow_ttm")), "pe_ttm": d.get("price_earnings_ttm"),
            "ev_ebitda": d.get("enterprise_value_ebitda_ttm"), "ps": d.get("price_sales_current"),
            "perf_1y_pct": d.get("Perf.Y"), "sector": d.get("sector"), "industry": d.get("industry"),
        })
    out["peers"] = rows
    med = {}
    for k in ("market_cap_usd", "revenue_ttm_usd", "rev_growth_last_fy_pct", "gross_margin_pct", "op_margin_pct",
              "net_margin_pct", "rnd_pct", "pe_ttm", "ev_ebitda", "ps", "perf_1y_pct"):
        vals = [r[k] for r in rows if not r["is_subject"] and r.get(k) is not None and (k not in ("pe_ttm", "ev_ebitda") or r[k] > 0)]
        med[k] = round(statistics.median(vals), 2) if vals else None
    out["peer_median"] = med
    if a.segments:
        seg = json.loads(a.segments)
        out["segments"] = {k: [mapping.get(p, p) for p in v] for k, v in seg.items()}
    out["fx"] = {k: {"rate": v[0], "source": v[1]} for k, v in fx_cache.items()}
    write_json(a.out, out)


if __name__ == "__main__":
    main()
