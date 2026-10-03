"""Build schema-valid FIXTURE sidecars from real run_all.py output, to test the dashboard
and validator without running the full multi-agent analysis.

Numbers (price, financials, multiples, manipulation inputs, news) are real script output;
every qualitative field is placeholder text prefixed "[fixture]". Never publish these.

Usage: python tests/make_fixture.py --data <dir with TICKER/ subfolders from run_all.py> --out <report dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from scores import SUBS, c5_from_banks, compute  # noqa: E402


def Lx(en, tr=None):
    return {"en": f"[fixture] {en}", "tr": f"[örnek] {tr or en}"}


def load(d, f):
    with open(os.path.join(d, f), encoding="utf-8") as fh:
        return json.load(fh)


def build(tick_dir: str) -> dict:
    p, fin, mul, news, risk = (load(tick_dir, f) for f in ("price.json", "financials.json", "multiples.json", "news.json", "risk.json"))
    banks = load(tick_dir, "banks.json") if os.path.exists(os.path.join(tick_dir, "banks.json")) else {"banks": [], "local_candidates": [], "summary": {}}
    q, cur = p["quote"], fin.get("currency") or p["quote"].get("currency")
    tv = p["tv_symbol"]
    ticker = tv.split(":")[1]
    ann = fin["annual"]
    years = [{"fy": r["fy"], "revenue": r.get("revenue"), "revenue_yoy_pct": r.get("revenue_yoy_pct"), "gross_profit": r.get("gross_profit"),
              "op_income": r.get("operating_income"), "net_income": r.get("net_income"), "net_income_yoy_pct": r.get("net_income_yoy_pct"),
              "eps": r.get("eps_diluted"), "fcf": r.get("fcf"), "gross_margin_pct": r.get("gross_margin_pct"), "op_margin_pct": r.get("op_margin_pct"),
              "net_margin_pct": r.get("net_margin_pct"), "revenue_usd": r.get("revenue_usd"), "net_income_usd": r.get("net_income_usd")} for r in ann]
    ttm = fin["ttm"]
    years.insert(0, {"fy": "TTM", "ttm": True, "revenue": ttm.get("revenue"), "net_income": ttm.get("net_income"), "gross_profit": ttm.get("gross_profit"),
                     "op_income": ttm.get("operating_income"), "fcf": ttm.get("fcf"), "eps": ttm.get("eps_diluted"),
                     "gross_margin_pct": ttm.get("gross_margin_pct"), "op_margin_pct": ttm.get("op_margin_pct"), "net_margin_pct": ttm.get("net_margin_pct")})
    g = fin["growth"]
    subs = {c: {k: round(5 + (hash(ticker + k) % 40) / 10, 1) for k in w} for c, w in SUBS.items()}
    mi = risk["manipulation_index"]
    inputs = []
    for i in mi["inputs"]:
        pts = i["points"] if i["points"] is not None else (0 if "Halts" in i["input"] else 1)
        inputs.append({"input": {"en": i["input"], "tr": i["input"]}, "value": i["value"], "points": pts})
    tot = sum(i["points"] for i in inputs)
    lvl = "L" if tot <= 5 else "M" if tot <= 11 else "H"
    subs["C4b"]["manipulation"] = {"L": 10, "M": 5, "H": 1}[lvl]
    s5 = build_s5(banks, p)
    c5 = c5_from_banks({"summary": {"covered_total": sum(r["covered"] for r in s5["rows"]), **{k: s5["consensus"][k] for k in ("buy", "hold", "sell")},
                                    "median_upside_pct": s5["consensus"]["median_upside_pct"], "raises_window": s5["consensus"]["raises"],
                                    "lowers_window": s5["consensus"]["lowers"]}})
    subs["C5"] = {k: c5[k] for k in SUBS["C5"]}
    res = compute({c: dict(v) for c, v in subs.items()})
    comps = {c: {"score": res["components"][c], "subs": [{"key": k, "label": {"en": k.replace("_", " "), "tr": k.replace("_", " ")},
                                                          "weight": w, "score": subs[c][k], "note": Lx("sub-score rationale")} for k, w in SUBS[c].items()]}
             for c in SUBS}
    price = q.get("price") or 0
    scen = [{"name": "bear", "move_pct": -8.0, "probability_pct": 25, "driver": Lx("bear driver")},
            {"name": "base", "move_pct": 1.5, "probability_pct": 50, "driver": Lx("base driver")},
            {"name": "bull", "move_pct": 9.0, "probability_pct": 25, "driver": Lx("bull driver")}]
    for s in scen:
        s["target"] = round(price * (1 + s["move_pct"] / 100), 2)
    exp = round(sum(s["move_pct"] * s["probability_pct"] for s in scen) / 100, 2)
    mc = mul["current"]
    a5 = mul["avg_5y"]
    mults = [{"name": n, "current": mc.get(k), "avg_5y": a5.get(h) if h else None, "peer_median": None, "premium_pct": None, "verdict": "fair"}
             for n, k, h in (("P/E", "pe_ttm", "pe"), ("EV/EBITDA", "ev_ebitda", "ev_ebitda"), ("P/S", "ps", "ps"), ("P/B", "pb", None), ("P/FCF", "p_fcf", None))]
    swot_item = lambda q_, i: {"item": Lx(f"{q_} item {i}"), "evidence": Lx("metric + source"), "impact": "LMH"[i % 3],  # noqa: E731
                                "horizon": ["short", "medium", "long"][i % 3], "probability_pct": 40 if q_ in "OT" else None, "source": "s1"}
    rev = ann[0].get("revenue") if ann else None
    return {
        "schema_version": "1.0",
        "meta": {"ticker": ticker, "tv_symbol": tv, "yahoo_symbol": p["yahoo_symbol"], "name": q.get("name") or ticker, "exchange": tv.split(":")[0],
                 "country": None, "sector": q.get("sector"), "industry": q.get("industry"), "currency": cur, "fx_to_usd": q.get("fx_to_usd"),
                 "data_timestamp": p["fetched_at"], "report_date": p["fetched_at"][:10], "classification": "Transitional", "data_status": "ok"},
        "snapshot": {"price": price, "change_1d_pct": q.get("change_1d_pct"), "perf_1m_pct": q.get("perf_1m_pct"), "perf_ytd_pct": q.get("perf_ytd_pct"),
                     "perf_1y_pct": q.get("perf_1y_pct"), "market_cap": q.get("market_cap"), "market_cap_usd": q.get("market_cap_usd"),
                     "ev": q.get("enterprise_value"), "high_52w": q.get("high_52w"), "low_52w": q.get("low_52w"), "pe_ttm": mc.get("pe_ttm"),
                     "ev_ebitda": mc.get("ev_ebitda"), "rev_cagr_5y": g["revenue"]["cagr_5y"], "rev_cagr_5y_usd": (g.get("revenue_usd") or {}).get("cagr_5y"),
                     "net_margin_pct": ann[0].get("net_margin_pct") if ann else None},
        "price_series": p["series"],
        "scores": {"short": res["short"], "medium": res["medium"], "long": res["long"], "components": comps},
        "tags": {"manipulation": lvl, "ceo_trust": "M", "news_risk": "M", "bank_view": s5["summary_tag"]},
        "s1": {"summary_today": Lx("what the company does today"), "summary_future": Lx("future plans"), "summary_futureproof": Lx("future-proof view"),
               "segments": [{"name": Lx("Segment A"), "revenue": rev * 0.6 if rev else None, "pct": 60, "yoy_pct": 5, "op_margin_pct": 20, "products": Lx("products"), "source": "s1"},
                            {"name": Lx("Segment B"), "revenue": rev * 0.4 if rev else None, "pct": 40, "yoy_pct": -2, "op_margin_pct": 12, "products": Lx("products"), "source": "s1"}],
               "geography": [{"region": Lx("Region 1"), "pct": 55}, {"region": Lx("Region 2"), "pct": 45}],
               "value_chain": [{"role": Lx(r), "company": c, "provides": Lx("input"), "dependency": d, "substitutable": sb, "source": "s1"}
                               for r, c, d, sb in (("supplier", "Supplier Co", "H", False), ("customer", "Customer Co", "M", True), ("partner", "Partner Co", "L", True))],
               "roadmap": [{"initiative": Lx("Initiative 1"), "target": Lx("market"), "timeline": "2027", "investment": "n/a", "status": "development", "goal": Lx("goal"), "source": "s1"},
                           {"initiative": Lx("Initiative 2"), "target": Lx("market"), "timeline": "2028", "investment": None, "status": "announced", "goal": Lx("goal"), "source": "s1"}],
               "futureproof": {"classification": "Transitional", "rnd_pct": ann[0].get("rnd_pct") if ann else None, "rnd_peer_median_pct": None,
                               "new_product_rev_pct": None, "ip_position": Lx("ip"), "disruption_exposure": "M", "moat_years": 5}},
        "s2": {"markets": [{"segment": Lx("Segment A"), "tam": 1e11, "tam_unit": "USD", "cagr_pct": 6, "our_share_pct": 20, "share_trend": "up", "leader": ticker,
                            "shares": [{"company": ticker, "pct": 20}, {"company": "Rival 1", "pct": 15}, {"company": "Rival 2", "pct": 10}, {"company": "Others", "pct": 55}], "source": "s1"}],
               "peers": [{"ticker": ticker, "name": q.get("name") or ticker, "is_subject": True, "market_cap_usd": q.get("market_cap_usd"), "pe": mc.get("pe_ttm")},
                         {"ticker": "PEER", "name": "[fixture] Peer", "is_subject": False}],
               "diff_matrix": {"companies": [ticker, "PEER"], "rows": [{"feature": Lx(f"capability {i}"), "values": [v, w]} for i, (v, w) in enumerate((("lead", "par"), ("par", "lead"), ("behind", "lead")))]},
               "better_worse": {"better": [{"item": Lx("better 1"), "metric": "+5pp"}], "worse": [{"item": Lx("worse 1"), "metric": "-3pp"}]},
               "swot": {k: [swot_item(k, i) for i in range(5)] for k in "SWOT"}},
        "s3": {"currency": cur, "years": years,
               "growth": [{"metric": {"en": k, "tr": k}, "cagr_5y": g[k]["cagr_5y"], "cagr_3y": g[k]["cagr_3y"], "last_yoy": g[k]["last_yoy"], "peer_median": None} for k in g],
               "anomalies": [{"fy": ann[-1]["fy"], "metric": Lx("net income"), "change_pct": ann[-1].get("net_income_yoy_pct"), "cause": Lx("cause"), "one_off": True, "impact": "M", "duration": Lx("2 quarters"), "source": "s1"}],
               "balance": [{"metric": {"en": k, "tr": k}, "value": ann[0].get(k), "trend": "flat"} for k in ("cash", "total_debt", "net_debt_to_ebitda", "current_ratio", "interest_coverage", "equity_ratio_pct")]},
        "s4": {"multiples": mults,
               "worth": {"market_cap": q.get("market_cap"), "ev": q.get("enterprise_value"), "fair_low": round(price * 0.85, 2), "fair_mid": round(price, 2), "fair_high": round(price * 1.2, 2),
                         "upside_pct": 0.0, "methods": [{"method": Lx("multiples"), "value": round(price, 2), "assumptions": Lx("assumptions")}]},
               "consensus": {"low": mc.get("target_low"), "mean": mc.get("target_mean"), "high": mc.get("target_high"),
                             "buy": (mc.get("rating_buy") or 0) + (mc.get("rating_overweight") or 0), "hold": mc.get("rating_hold"), "sell": (mc.get("rating_sell") or 0) + (mc.get("rating_underweight") or 0)},
               "forecast_1m": {"scenarios": scen, "expected_move_pct": exp, "catalysts": [{"date": q.get("next_earnings_date") or "n/a", "event": Lx("earnings")}],
                               "inputs": {"rsi": q.get("rsi_14"), "vs_sma50_pct": q.get("vs_sma50_pct"), "vs_sma200_pct": q.get("vs_sma200_pct"), "vol_30d_pct": q.get("realized_vol_30d_ann_pct")}},
               "manipulation": {"level": lvl, "total_points": tot, "inputs": inputs},
               "ceo": {"name": (risk.get("ceo") or {}).get("name") or "n/a", "since": None, "score": 5.5, "trust": "M",
                       "rows": [{"criterion": Lx(f"criterion {i}"), "value": Lx("value"), "points": 0.8, "source": "s1"} for i in range(7)]},
               "world_exposure": [{"theme": Lx("theme"), "channel": Lx("channel"), "direction": "-", "risk": "M", "horizon": "short", "confidence": "M"}],
               "news": [{"date": n["date"], "outlet": n["outlet"], "headline": n["headline"], "url": n["url"], "direction": "0", "impact": "L", "horizon": "short", "priced_in": "partial"}
                        for n in news["items"][:6]]},
        "s5": s5,
        "sources": [{"id": "s1", "title": "[fixture] source", "url": "https://www.tradingview.com/", "date": p["fetched_at"][:10]}],
    }


def build_s5(banks: dict, p: dict) -> dict:
    """Section 5 from banks.json; topics are placeholders. Local rows: only covered ones (max 3)."""
    import statistics
    cand = [r for r in banks.get("local_candidates", []) if r.get("covered") and r.get("rating")][:3]
    rows = []
    for r in banks.get("banks", []) + cand:
        cov = bool(r.get("covered"))
        arts = r.get("coverage_articles", [])
        rep = cov and bool(arts)
        rows.append({
            "bank": r["bank"], "role": r["role"], "covered": cov, "rating_raw": r.get("rating_raw") if cov else None,
            "rating": r.get("rating") if cov else None, "target": r.get("target") if cov else None,
            "target_currency": r.get("target_currency") if cov else None, "target_listing": r.get("target_listing") if cov else None,
            "target_report_ccy": r.get("target_report_ccy") if cov else None, "upside_pct": r.get("upside_pct") if cov else None,
            "date": r.get("date") if cov else None,
            "action": ({"en": f"{r.get('action')} PT {r.get('prior_target')}→{r.get('target')}", "tr": f"{r.get('action')} HF {r.get('prior_target')}→{r.get('target')}"}
                       if cov and r.get("action") else None),
            "rating_source": ("broker_page" if r["role"] == "local" else "yahoo") if cov else None,
            "important": [Lx("thesis driver from note")] if rep else [], "niche": [Lx("specific datapoint from note")] if rep else [],
            "topics_status": "reported" if rep else ("not_reported" if cov else "no_coverage"),
            "topic_sources": [a["url"] for a in arts[:2]] if rep else [],
            "history": [{"date": h["date"], "rating": h.get("rating"), "target": h.get("target")} for h in r.get("history", [])] if cov else [],
            "source": (r.get("source") or {}).get("url") if cov else None,
        })
    cov = [r for r in rows if r["covered"]]
    ups = [r["upside_pct"] for r in cov if r["upside_pct"] is not None]
    tg = [r["target_report_ccy"] for r in cov if r["target_report_ccy"] is not None]
    cons = {"buy": sum(r["rating"] == "Buy" for r in cov), "hold": sum(r["rating"] == "Hold" for r in cov),
            "sell": sum(r["rating"] == "Sell" for r in cov), "covered_fixed": sum(r["covered"] for r in rows if r["role"] == "fixed"),
            "median_target": round(statistics.median(tg), 2) if tg else None,
            "median_upside_pct": round(statistics.median(ups), 2) if ups else None,
            "raises": banks.get("summary", {}).get("raises_window", 0), "lowers": banks.get("summary", {}).get("lowers_window", 0)}
    tag = ("Insufficient" if len(cov) < 2 else "Buy-majority" if cons["buy"] > len(cov) / 2
           else "Sell-majority" if cons["sell"] > len(cov) / 2 else "Mixed")
    return {"window_days": banks.get("window_days", 180), "price_currency": banks.get("price_currency") or p["quote"].get("currency"),
            "rows": rows, "consensus": cons, "summary_tag": tag}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for t in sorted(os.listdir(a.data)):
        d = os.path.join(a.data, t)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "price.json")):
            rep = build(d)
            out = os.path.join(a.out, f"{rep['meta']['ticker']}.json")
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(rep, fh, ensure_ascii=False, indent=1)
            print("wrote", out)


if __name__ == "__main__":
    main()
