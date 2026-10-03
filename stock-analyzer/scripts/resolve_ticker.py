"""Resolve company names / tickers to listing info.

Usage:
  python resolve_ticker.py "aapl, nvidia, THYAO, asml" [--out resolved.json]

Primary: TradingView symbol search. Fallback: Yahoo search.
Sets "supported": false for ETFs/funds/crypto, "ambiguous": true when the
best match is unclear (agent must ask the user, showing "candidates").
"""
from __future__ import annotations

import argparse
import re

from common import (TV_SEARCH_URL, YAHOO_EXCH_TO_TV, YAHOO_SEARCH_URL, http, now_iso,
                    split_symbol, tv_scan, write_json, yahoo_symbol_for)

MAJOR_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "BIST", "XETR", "LSE", "EURONEXT", "TSE", "HKEX", "SIX", "TSX", "ASX", "KRX", "NSE"}
NON_EQUITY = {"ETF", "MUTUALFUND", "CRYPTOCURRENCY", "INDEX", "FUTURE", "CURRENCY", "OPTION"}


def strip_tags(s: str) -> str:
    return re.sub(r"</?em>", "", s or "")


def tv_candidates(text: str) -> list[dict]:
    r = http("GET", TV_SEARCH_URL, params={
        "text": text, "hl": 1, "lang": "en", "domain": "production", "search_type": "stocks"},
        headers={"Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"})
    out = []
    for s in r.json().get("symbols", []):
        if s.get("type") not in ("stock", "dr"):
            continue
        ex = s.get("source_id") or s.get("exchange")
        out.append({
            "ticker": strip_tags(s.get("symbol")),
            "exchange": ex,
            "name": strip_tags(s.get("description")),
            "country": s.get("country"),
            "currency": s.get("currency_code"),
            "isin": s.get("isin"),
            "cik": s.get("cik_code"),
            "primary": bool(s.get("is_primary_listing")),
            "type": s.get("type"),
        })
    return out


def yahoo_lookup(text: str) -> list[dict]:
    r = http("GET", YAHOO_SEARCH_URL, params={"q": text, "quotesCount": 8, "newsCount": 0})
    return r.json().get("quotes", [])


def finalize(c: dict, source: str) -> dict:
    tv_symbol = f"{c['exchange']}:{c['ticker']}"
    res = {
        "ticker": c["ticker"], "exchange": c["exchange"], "tv_symbol": tv_symbol,
        "yahoo_symbol": yahoo_symbol_for(c["exchange"], c["ticker"], c.get("country")),
        "name": c["name"], "country": c.get("country"), "currency": c.get("currency"),
        "isin": c.get("isin"), "cik": c.get("cik"), "resolved_by": source,
    }
    try:  # enrich with sector/industry from the scanner
        d = tv_scan([tv_symbol], ["sector", "industry", "currency", "fundamental_currency_code"]).get(tv_symbol, {})
        res.update({"sector": d.get("sector"), "industry": d.get("industry"),
                    "currency": d.get("currency") or res["currency"],
                    "reporting_currency": d.get("fundamental_currency_code")})
    except Exception as e:  # noqa: BLE001
        res["enrich_error"] = str(e)
    return res


def resolve_one(raw: str) -> dict:
    text = raw.strip()
    out = {"input": raw, "supported": True, "ambiguous": False, "candidates": []}
    ex_hint, tick_hint = split_symbol(text)
    query = tick_hint if ex_hint else text
    # Yahoo first only to detect non-equities (ETF, crypto...).
    try:
        yq = yahoo_lookup(query)
        if yq and yq[0].get("quoteType") in NON_EQUITY and yq[0].get("symbol", "").upper().split(".")[0] == query.upper():
            out.update(supported=False, reason=f"{yq[0].get('quoteType')} - not a single company")
            return out
    except Exception:  # noqa: BLE001
        yq = []
    cands = []
    try:
        cands = tv_candidates(query)
    except Exception as e:  # noqa: BLE001
        out["tv_error"] = str(e)
    if ex_hint:
        cands = [c for c in cands if c["exchange"] == ex_hint] or cands
    if cands:
        exact = [c for c in cands if c["ticker"].upper() == query.upper()]
        exact_primary = [c for c in exact if c["primary"]]
        primary = [c for c in cands if c["primary"]] or cands
        if exact_primary:
            # "amd" is also a ticker on ASX and TASE; TradingView ranks by relevance, so the
            # top hit on a major exchange is unambiguous. Exotic top hits ("TM" -> SET:TM) ask.
            best = exact_primary[0]
            amb = len({c["name"] for c in exact_primary}) > 1 and not (
                best is cands[0] and best["exchange"] in MAJOR_EXCHANGES)
        elif exact:
            # GOTCHA: "lufthansa" exactly matches BET:LUFTHANSA (Budapest cross-listing).
            # Prefer the same company's primary listing (XETR:LHA) when one exists.
            same = [c for c in cands if c["primary"] and c["name"].lower() == exact[0]["name"].lower()]
            best, amb = (same[0] if same else exact[0]), False
        else:
            best = primary[0]
            amb = not best["name"].lower().startswith(query.lower().split()[0])
        out.update(finalize(best, "tradingview"))
        out["ambiguous"] = amb
        out["candidates"] = [f"{c['exchange']}:{c['ticker']} - {c['name']} ({c['country']})" for c in primary[:5]]
        return out
    # Fallback: Yahoo equities
    eq = [q for q in yq if q.get("quoteType") == "EQUITY"]
    if eq:
        q = eq[0]
        sym = q["symbol"]
        tick = sym.split(".")[0]
        ex = YAHOO_EXCH_TO_TV.get(q.get("exchange"), q.get("exchange"))
        out.update(finalize({"ticker": tick, "exchange": ex, "name": q.get("longname") or q.get("shortname"),
                             "country": None, "currency": None}, "yahoo"))
        out["yahoo_symbol"] = sym
        out["candidates"] = [f"{x['symbol']} - {x.get('longname') or x.get('shortname')}" for x in eq[:5]]
        out["ambiguous"] = len(eq) > 1 and not (q.get("longname") or "").lower().startswith(query.lower())
        return out
    out.update(supported=False, reason="no listing found")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", help='comma-separated names/tickers, e.g. "aapl, nvidia, BIST:THYAO"')
    ap.add_argument("--out")
    a = ap.parse_args()
    items = [x for x in (s.strip() for s in a.inputs.split(",")) if x]
    results = [resolve_one(x) for x in items]
    write_json(a.out, {"fetched_at": now_iso(), "source": "TradingView symbol search; Yahoo search fallback",
                       "results": results, "errors": [r.get("tv_error") for r in results if r.get("tv_error")]})


if __name__ == "__main__":
    main()
