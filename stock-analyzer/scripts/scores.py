"""Deterministic scoring (references/scoring.md). Agents MUST use this, never hand-compute.

Usage:
  python scores.py --subs subs.json            # {"C1": {"revenue_quality": 7, ...}, ...}
  python scores.py --report AAPL.json          # recompute from a sidecar's scores.components

Prints a markdown computation table + JSON {components, short, medium, long}.
"""
from __future__ import annotations

import argparse
import json
import sys

SUBS = {
    "C1": {"revenue_quality": 0.30, "value_chain": 0.20, "roadmap": 0.20, "future_proof": 0.30},
    "C2": {"market_share": 0.40, "moat": 0.30, "swot_balance": 0.30},
    "C3": {"revenue_growth": 0.25, "profit_growth_margins": 0.25, "earnings_quality": 0.20, "balance_sheet": 0.30},
    "C4a": {"multiples": 0.50, "fair_value_upside": 0.50},
    "C4b": {"expected_move_1m": 0.35, "news_risk": 0.30, "manipulation": 0.15, "ceo_trust": 0.20},
    "C5": {"rating_mix": 0.40, "target_upside": 0.35, "revision_trend": 0.25},
}
NAMES = {"C1": "Business", "C2": "Competition", "C3": "Financials", "C4a": "Valuation", "C4b": "Momentum & Risk",
         "C5": "Bank consensus"}
HORIZON = {
    "short": {"C1": 0.05, "C2": 0.10, "C3": 0.10, "C4a": 0.20, "C4b": 0.45, "C5": 0.10},
    "medium": {"C1": 0.15, "C2": 0.15, "C3": 0.20, "C4a": 0.20, "C4b": 0.15, "C5": 0.15},
    "long": {"C1": 0.30, "C2": 0.20, "C3": 0.25, "C4a": 0.10, "C4b": 0.05, "C5": 0.10},
}
assert all(abs(sum(w.values()) - 1) < 1e-9 for w in HORIZON.values()), "horizon weights must sum to 1"
MANIPULATION_SUBSCORE = {"L": 10, "M": 5, "H": 1, "Low": 10, "Medium": 5, "High": 1}


def r1(x: float) -> float:
    return float(f"{x + 1e-9:.1f}")


def compute(subs: dict) -> dict:
    comps = {}
    for c, weights in SUBS.items():
        given = subs.get(c, {})
        missing = [k for k in weights if k not in given]
        if missing:
            raise ValueError(f"{c} missing sub-scores: {missing}")
        for k, v in given.items():
            if k == "manipulation" and isinstance(v, str):
                given[k] = v = MANIPULATION_SUBSCORE[v]
            if not 0 <= float(v) <= 10:
                raise ValueError(f"{c}.{k}={v} outside 0-10")
        comps[c] = r1(sum(float(given[k]) * w for k, w in weights.items()))
    finals = {h: r1(sum(comps[c] * w for c, w in ws.items())) for h, ws in HORIZON.items()}
    return {"components": comps, **finals}


def c5_from_banks(b: dict) -> dict:
    """Deterministic C5 sub-scores from banks.json summary (references/scoring.md).
    The agent may override only with cited evidence (e.g. a press-verified bank row it added)."""
    sm = b.get("summary", {})
    n = sm.get("covered_total") or 0
    if n < 2:
        return {"rating_mix": 5.0, "target_upside": 5.0, "revision_trend": 5.0, "_insufficient": True}
    buy, hold, sell = sm.get("buy", 0), sm.get("hold", 0), sm.get("sell", 0)
    rated = buy + hold + sell or 1
    mix = (buy * 10 + hold * 5 + sell * 0) / rated          # all Buy 10, all Hold 5, all Sell 0
    up = sm.get("median_upside_pct")
    # linear: -15% -> 0, 0% -> 5, +30% -> 10
    tu = 5.0 if up is None else (max(0.0, 5 + up / 3) if up < 0 else min(10.0, 5 + up / 6))
    r, l = sm.get("raises_window", 0), sm.get("lowers_window", 0)
    rev = 5.0 if r + l == 0 else 10 * r / (r + l)
    return {"rating_mix": r1(mix), "target_upside": r1(tu), "revision_trend": r1(rev), "_insufficient": False}


def from_report(rep: dict) -> dict:
    comps = rep["scores"]["components"]
    return {c: {s["key"]: s["score"] for s in comps[c]["subs"]} for c in SUBS}


def table(res: dict) -> str:
    lines = ["| Component | Score | Short w | Medium w | Long w |", "|---|---|---|---|---|"]
    for c in SUBS:
        lines.append(f"| {c} {NAMES[c]} | {res['components'][c]} | {int(HORIZON['short'][c]*100)}% | "
                     f"{int(HORIZON['medium'][c]*100)}% | {int(HORIZON['long'][c]*100)}% |")
    lines.append(f"| **Final** | | **{res['short']}/10** | **{res['medium']}/10** | **{res['long']}/10** |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--subs")
    g.add_argument("--report")
    g.add_argument("--banks")
    a = ap.parse_args()
    if a.banks:
        with open(a.banks, encoding="utf-8") as f:
            print(json.dumps(c5_from_banks(json.load(f))))
        return
    if a.subs:
        with open(a.subs, encoding="utf-8") as f:
            subs = json.load(f)
    else:
        with open(a.report, encoding="utf-8") as f:
            subs = from_report(json.load(f))
    res = compute(subs)
    sys.stdout.reconfigure(encoding="utf-8")
    print(table(res))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
