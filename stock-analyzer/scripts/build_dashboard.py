"""Embed validated sidecars into templates/dashboard.html -> <dir>/dashboard.html.

Usage: python build_dashboard.py --dir stock-reports/2026-10-03 [--tickers AAPL,NVDA] [--out ...]
Reads <dir>/<TICKER>.json (all *.json in <dir> except world-context.json unless --tickers given)
and <dir>/world-context.json if present. Stocks whose sidecar fails validation are embedded
with meta.data_status="unavailable" placeholders instead of being dropped.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_report import validate  # noqa: E402

TEMPLATE = os.path.join(HERE, "..", "templates", "dashboard.html")
MARKER = "/*__REPORT_DATA__*/null"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tickers")
    ap.add_argument("--out")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.tickers:
        files = [os.path.join(a.dir, f"{t.strip().upper()}.json") for t in a.tickers.split(",")]
    else:
        files = sorted(f for f in glob.glob(os.path.join(a.dir, "*.json"))
                       if os.path.basename(f) not in ("world-context.json", "resolved.json"))
    stocks, failed = [], []
    for f in files:
        tick = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(f):
            failed.append({"ticker": tick, "reason": "sidecar missing"})
            continue
        errs, _ = validate(f)
        if errs:
            failed.append({"ticker": tick, "reason": f"{len(errs)} validation errors: {errs[0][:120]}"})
            continue
        with open(f, encoding="utf-8") as fh:
            stocks.append(json.load(fh))
    world = None
    wp = os.path.join(a.dir, "world-context.json")
    if os.path.exists(wp):
        with open(wp, encoding="utf-8") as fh:
            world = json.load(fh)
    data = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "mode": "single" if len(stocks) + len(failed) == 1 else "multi",
            "stocks": stocks, "unavailable": failed, "world": world}
    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()
    if MARKER not in tpl:
        sys.exit(f"template marker {MARKER} not found in {TEMPLATE}")
    ticks = [x["meta"]["ticker"] for x in stocks] + [x["ticker"] for x in failed]
    title = (f"{ticks[0]} Stock Analysis" if len(ticks) == 1 else
             f"{', '.join(ticks)} Analysis" if len(ticks) <= 4 else f"{len(ticks)}-Stock Comparison")
    tpl = tpl.replace("__TITLE__", title)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace(MARKER, payload)
    out = a.out or os.path.join(a.dir, "dashboard.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {out}: {len(stocks)} stocks, {len(failed)} unavailable, {len(html)//1024} KB")
    for x in failed:
        print(f"  UNAVAILABLE {x['ticker']}: {x['reason']}")


if __name__ == "__main__":
    main()
