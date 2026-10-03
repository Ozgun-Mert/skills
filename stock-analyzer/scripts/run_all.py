"""Fetch every data block for one stock into <outdir>/.

Usage (values from resolve_ticker.py output):
  python run_all.py --tv NASDAQ:AAPL --yahoo AAPL --name "Apple Inc." --outdir stock-reports/2026-10-03/data/AAPL \
      [--cik 320193] [--exchange NASDAQ] [--aliases "..."] [--news-days 30]
  python run_all.py --input "turkish airlines" --outdir ...     # resolves first (non-ambiguous only)

Writes: price.json, financials.json, multiples.json, news.json, risk.json, run_summary.json
Peers are separate (agent picks them per segment): fetch_peers.py --out <outdir>/peers.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script: str, args: list[str]) -> tuple[str, int, str]:
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=900)
    return script, p.returncode, (p.stdout + p.stderr).strip()[-600:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    ap.add_argument("--tv")
    ap.add_argument("--yahoo")
    ap.add_argument("--name")
    ap.add_argument("--cik")
    ap.add_argument("--exchange")
    ap.add_argument("--aliases", default="")
    ap.add_argument("--news-days", type=int, default=30)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    if a.input and not a.tv:
        sys.path.insert(0, HERE)
        from resolve_ticker import resolve_one
        r = resolve_one(a.input)
        if not r.get("supported") or r.get("ambiguous"):
            sys.exit(f"cannot auto-resolve '{a.input}': {json.dumps(r, ensure_ascii=False)}")
        a.tv, a.yahoo, a.name, a.cik, a.exchange = r["tv_symbol"], r["yahoo_symbol"], r["name"], r.get("cik"), r["exchange"]
    if not (a.tv and a.yahoo and a.name):
        ap.error("--tv, --yahoo and --name are required (or --input)")
    a.exchange = a.exchange or a.tv.split(":")[0]
    ticker = a.tv.split(":")[1]
    os.makedirs(a.outdir, exist_ok=True)
    o = lambda f: os.path.join(a.outdir, f)  # noqa: E731
    cik = ["--cik", str(a.cik)] if a.cik else []
    al = ["--aliases", a.aliases] if a.aliases else []

    results = []
    with ThreadPoolExecutor(3) as ex:
        stage1 = [
            ex.submit(run, "fetch_price.py", ["--tv", a.tv, "--yahoo", a.yahoo, "--out", o("price.json")]),
            ex.submit(run, "fetch_financials.py", ["--tv", a.tv, "--yahoo", a.yahoo, *cik, "--out", o("financials.json")]),
            ex.submit(run, "fetch_news.py", ["--name", a.name, "--ticker", ticker, "--exchange", a.exchange, *cik, *al,
                                             "--days", str(a.news_days), "--out", o("news.json")]),
        ]
        results += [f.result() for f in stage1]
        stage2 = [
            ex.submit(run, "fetch_multiples.py", ["--tv", a.tv, "--yahoo", a.yahoo, "--fin", o("financials.json"),
                                                  "--out", o("multiples.json")]),
            ex.submit(run, "fetch_risk_inputs.py", ["--tv", a.tv, "--yahoo", a.yahoo, "--name", a.name, *al,
                                                    "--price", o("price.json"), "--out", o("risk.json")]),
        ]
        results += [f.result() for f in stage2]

    summary = {"tv_symbol": a.tv, "yahoo_symbol": a.yahoo, "name": a.name, "outdir": a.outdir, "files": {}}
    print(f"{'file':<16} {'rc':>3} {'errors':>6}  notes")
    for script, rc, tail in results:
        fname = {"fetch_price.py": "price.json", "fetch_financials.py": "financials.json", "fetch_news.py": "news.json",
                 "fetch_multiples.py": "multiples.json", "fetch_risk_inputs.py": "risk.json"}[script]
        info = {"rc": rc, "errors": None, "notes": ""}
        try:
            with open(o(fname), encoding="utf-8") as f:
                d = json.load(f)
            info["errors"] = d.get("errors", [])
            if fname == "financials.json":
                info["notes"] = f"{d.get('years_available')} FY, cur={d.get('currency')}, discrepancies={len(d.get('discrepancies', []))}"
            elif fname == "price.json":
                q = d.get("quote", {})
                info["notes"] = f"price={q.get('price')} {q.get('currency')}, series={len((d.get('series') or {}).get('dates', []))}d"
            elif fname == "news.json":
                info["notes"] = f"{d.get('count')} tier-1 items, {len(d.get('official', []))} official"
            elif fname == "multiples.json":
                c = d.get("current", {})
                info["notes"] = f"P/E={c.get('pe_ttm')}, EV/EBITDA={c.get('ev_ebitda')}"
            elif fname == "risk.json":
                m = d.get("manipulation_index", {})
                info["notes"] = f"manip partial={m.get('partial_total')} missing={len(m.get('missing_inputs', []))}"
        except Exception as e:  # noqa: BLE001
            info["errors"] = [f"no output: {e}; {tail}"]
        summary["files"][fname] = info
        print(f"{fname:<16} {rc:>3} {len(info['errors'] or []):>6}  {info['notes']}")
        for err in (info["errors"] or [])[:3]:
            print(f"{'':<27}! {str(err)[:140]}")
    with open(o("run_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
