"""Risk inputs: ownership, short interest, insiders, CEO data, regulatory/halt headlines,
and the deterministic Manipulation Susceptibility Index (references/indices.md).

Usage: python fetch_risk_inputs.py --tv NASDAQ:AAPL --yahoo AAPL --name "Apple Inc." \
          [--aliases "..."] [--price data/AAPL/price.json] [--out data/AAPL/risk.json]
"""
from __future__ import annotations

import argparse

from common import fx_to_usd, load_json, now_iso, tv_scan, write_json
from fetch_news import OUTLETS, collect, short_name

REG_TERMS = ["halt", "suspended", "SEC", "SPK", "fraud", "probe", "investigation", "manipulation",
             "lawsuit", "charged", "fine", "fined", "antitrust", "short seller", "accounting"]


def band(v, cuts, reverse=False):
    """cuts = thresholds for 1,2,3 points (ascending). reverse: bigger value = safer."""
    if v is None:
        return None
    if reverse:
        return 0 if v > cuts[0] else 1 if v > cuts[1] else 2 if v > cuts[2] else 3
    return 0 if v < cuts[0] else 1 if v < cuts[1] else 2 if v < cuts[2] else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--aliases", default="")
    ap.add_argument("--price", help="price.json from fetch_price.py (for vol ratio)")
    ap.add_argument("--out")
    a = ap.parse_args()
    errors: list = []
    out = {"fetched_at": now_iso(), "tv_symbol": a.tv, "errors": errors,
           "sources": {"tradingview": f"https://www.tradingview.com/symbols/{a.tv.replace(':', '-')}/",
                       "yahoo": f"https://finance.yahoo.com/quote/{a.yahoo}/holders"}}
    tv = {}
    try:
        tv = tv_scan([a.tv], ["close", "currency", "market_cap_basic", "average_volume_30d_calc",
                              "float_shares_percent_current"]).get(a.tv) or {}
    except Exception as e:  # noqa: BLE001
        errors.append(f"TradingView: {e}")
    info, own, ceo, insiders = {}, {}, None, None
    try:
        import yfinance as yf
        t = yf.Ticker(a.yahoo)
        info = t.info or {}
        own = {
            "short_pct_float": round(info["shortPercentOfFloat"] * 100, 2) if info.get("shortPercentOfFloat") is not None else None,
            "days_to_cover": info.get("shortRatio"),
            "insiders_pct": round(info["heldPercentInsiders"] * 100, 2) if info.get("heldPercentInsiders") is not None else None,
            "institutions_pct": round(info["heldPercentInstitutions"] * 100, 2) if info.get("heldPercentInstitutions") is not None else None,
        }
        try:
            ih = t.institutional_holders
            if ih is not None and not ih.empty:
                col = "pctHeld" if "pctHeld" in ih.columns else None
                own["top_institutions"] = [{"holder": r["Holder"], "pct": round(float(r[col]) * 100, 2) if col else None}
                                           for _, r in ih.head(5).iterrows()]
        except Exception as e:  # noqa: BLE001
            errors.append(f"institutional_holders: {e}")
        tops = [x["pct"] for x in own.get("top_institutions", []) if x.get("pct") is not None]
        own["largest_holder_pct"] = max([own.get("insiders_pct") or 0] + tops) or None
        for o in info.get("companyOfficers", []):
            title = (o.get("title") or "").lower()
            if "ceo" in title or "chief executive" in title:
                ceo = {"name": o.get("name"), "title": o.get("title"), "age": o.get("age"),
                       "total_pay": o.get("totalPay"), "year_born": o.get("yearBorn")}
                break
        out["governance_iss"] = {k: info.get(k) for k in ("auditRisk", "boardRisk", "compensationRisk",
                                                          "shareHolderRightsRisk", "overallRisk")}
        try:
            ip = t.insider_purchases
            if ip is not None and not ip.empty:
                insiders = {str(r.iloc[0]): {"shares": r.get("Shares"), "trans": r.get("Trans")} for _, r in ip.iterrows()}
        except Exception as e:  # noqa: BLE001
            errors.append(f"insider_purchases: {e}")
        try:
            it = t.insider_transactions
            if it is not None and not it.empty:
                out["insider_transactions_recent"] = [
                    {"date": str(r.get("Start Date"))[:10], "insider": r.get("Insider"), "position": r.get("Position"),
                     "text": r.get("Text"), "shares": r.get("Shares"), "value": r.get("Value")}
                    for _, r in it.head(15).iterrows()]
        except Exception as e:  # noqa: BLE001
            errors.append(f"insider_transactions: {e}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Yahoo: {e}")
    out["ownership"] = own
    out["ceo"] = ceo
    out["insider_summary_6m"] = insiders

    names = [short_name(a.name)] + [x.strip() for x in a.aliases.split(",") if x.strip()]
    term = " OR ".join(f'"{n}"' for n in dict.fromkeys(names))
    reg_q = " OR ".join(REG_TERMS[:8])
    reg = collect([("regulatory", f"({term}) ({reg_q}) site:{d}") for d in OUTLETS.values()],
                  OUTLETS, 3 * 365, errors, names)
    import re
    # whole words only: "SEC" must not match "security"
    rx = re.compile("|".join(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])" for t in REG_TERMS), re.I)
    out["regulatory_headlines_3y"] = [r for r in reg if rx.search(r["headline"])][:20]

    vol_ratio = None
    if a.price:
        try:
            vol_ratio = load_json(a.price)["quote"].get("vol_ratio_30d_vs_1y")
        except Exception as e:  # noqa: BLE001
            errors.append(f"price.json: {e}")
    rate, _ = fx_to_usd(tv.get("currency"))
    mcap_usd = tv["market_cap_basic"] * rate if rate and tv.get("market_cap_basic") else None
    adv_usd = tv["close"] * tv["average_volume_30d_calc"] * rate if rate and tv.get("close") and tv.get("average_volume_30d_calc") else None
    float_pct = tv.get("float_shares_percent_current")
    inputs = [
        {"input": "Market cap (USD)", "value": mcap_usd, "points": band(mcap_usd, [50e9, 2e9, 3e8], reverse=True)},
        {"input": "Avg daily $ volume 30d (USD)", "value": adv_usd, "points": band(adv_usd, [5e8, 5e7, 5e6], reverse=True)},
        {"input": "Free float %", "value": float_pct, "points": band(float_pct, [80, 50, 20], reverse=True)},
        {"input": "Short interest % float", "value": own.get("short_pct_float"), "points": band(own.get("short_pct_float"), [3, 10, 20])},
        {"input": "Largest holder / insider %", "value": own.get("largest_holder_pct"), "points": band(own.get("largest_holder_pct"), [10, 30, 50])},
        {"input": "Halts / regulatory actions (3y)", "value": None, "points": None,
         "note": "AGENT: set 0 if none in regulatory_headlines_3y / filings, 3 if any confirmed"},
        {"input": "30d vol / 1y vol", "value": vol_ratio, "points": band(vol_ratio, [1.2, 1.6, 2.2])},
    ]
    known = [i["points"] for i in inputs if i["points"] is not None]
    total = sum(known)
    out["manipulation_index"] = {
        "inputs": inputs, "partial_total": total, "missing_inputs": [i["input"] for i in inputs if i["points"] is None],
        "level_if_complete": "Low" if total <= 5 else "Medium" if total <= 11 else "High",
        "thresholds": "0-5 Low, 6-11 Medium, >=12 High",
        "note": "Agent must finalize: score missing inputs (or treat unknown short interest as 1 pt and say so).",
    }
    write_json(a.out, out)


if __name__ == "__main__":
    main()
