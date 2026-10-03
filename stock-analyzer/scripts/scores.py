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
}
NAMES = {"C1": "Business", "C2": "Competition", "C3": "Financials", "C4a": "Valuation", "C4b": "Momentum & Risk"}
HORIZON = {
    "short": {"C1": 0.05, "C2": 0.10, "C3": 0.15, "C4a": 0.20, "C4b": 0.50},
    "medium": {"C1": 0.15, "C2": 0.20, "C3": 0.25, "C4a": 0.25, "C4b": 0.15},
    "long": {"C1": 0.30, "C2": 0.25, "C3": 0.25, "C4a": 0.15, "C4b": 0.05},
}
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
    a = ap.parse_args()
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
