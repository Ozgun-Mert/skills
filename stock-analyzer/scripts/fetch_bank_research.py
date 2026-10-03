"""Section 5 data: big-bank ratings, price targets and press coverage of their notes.

Usage:
  python fetch_bank_research.py --tv NASDAQ:NVDA --yahoo NVDA --name "NVIDIA Corporation" \
      [--aliases "Nvidia"] [--adr NVDA] [--price data/NVDA/price.json] [--days 180] [--out data/NVDA/banks.json]

Fixed banks (always 4 rows): JPMorgan, Bank of America, Morgan Stanley, Goldman Sachs.
Substitutes (<= 3 covered, newest first): Citi, UBS, Barclays, Deutsche Bank, Wells Fargo, HSBC.
BIST only - local brokers: Is Yatirim (parsed from its public company card), Yapi Kredi Yatirim,
Garanti BBVA Yatirim, Ak Yatirim, QNB Invest (press coverage + research page for the agent).

Ratings/targets: Yahoo upgrades_downgrades (primary listing, else the US ADR/listing).
Report topics: the script only finds coverage articles; the agent reads them. Never invent topics.
"""
from __future__ import annotations

import argparse
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from common import YAHOO_SEARCH_URL, fx_to_usd, http, load_json, now_iso, tv_scan, write_json
from fetch_news import OUTLETS, collect, short_name

# (display name, role, Yahoo "Firm" spellings - exact match, headline aliases)
# GOTCHA (verified 2026-10-03): Yahoo spells BofA "B of A Securities"; "Citizens" is a different
# firm, so Firm matching is exact, never substring.
FIXED = [
    ("JPMorgan", ["JP Morgan", "J.P. Morgan", "JPMorgan"], ["JPMorgan", "JP Morgan", "J.P. Morgan", "JPM"]),
    ("Bank of America", ["B of A Securities", "BofA Securities", "Bank of America", "Bank of America Securities", "Merrill Lynch"],
     ["Bank of America", "BofA", "B of A", "Merrill"]),
    ("Morgan Stanley", ["Morgan Stanley"], ["Morgan Stanley"]),
    ("Goldman Sachs", ["Goldman Sachs"], ["Goldman Sachs", "Goldman"]),
]
SUBSTITUTES = [
    ("Citi", ["Citigroup", "Citi"], ["Citigroup", "Citi"]),
    ("UBS", ["UBS"], ["UBS"]),
    ("Barclays", ["Barclays"], ["Barclays"]),
    ("Deutsche Bank", ["Deutsche Bank"], ["Deutsche Bank"]),
    ("Wells Fargo", ["Wells Fargo"], ["Wells Fargo"]),
    ("HSBC", ["HSBC"], ["HSBC"]),
]
LOCAL = [  # BIST brokers: (name, headline aliases, public research page)
    ("İş Yatırım", ["İş Yatırım", "Is Yatirim", "Is Investment", "İş Yatırım'"],
     "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={ticker}"),
    ("Yapı Kredi Yatırım", ["Yapı Kredi Yatırım", "Yapi Kredi Yatirim", "Yapı Kredi Invest"], "https://www.ykyatirim.com.tr/"),
    ("Garanti BBVA Yatırım", ["Garanti BBVA Yatırım", "Garanti BBVA Yatirim", "Garanti BBVA Securities"],
     "https://www.garantibbvayatirim.com.tr/arastirma/hisse-senedi-model-portfoyu"),
    ("Ak Yatırım", ["Ak Yatırım", "Ak Yatirim", "Ak Investment"], "https://www.akyatirim.com.tr/"),
    ("QNB Invest", ["QNB Invest", "QNB Yatırım", "QNB Finansinvest"], "https://www.qnbinvest.com.tr/arastirma"),
]
FINANCE_PRESS = {"Barron's": "barrons.com", "MarketWatch": "marketwatch.com", "Investing.com": "investing.com",
                 "TipRanks": "tipranks.com", "TheFly": "thefly.com", "StreetInsider": "streetinsider.com"}
BIST_PRESS = {"Bloomberg HT": "bloomberght.com"}

BUY = {"buy", "strong buy", "conviction buy", "overweight", "outperform", "market outperform", "sector outperform",
       "accumulate", "add", "positive", "top pick", "al", "endeksin üzerinde getiri", "endeksin uzerinde getiri"}
HOLD = {"hold", "neutral", "equal-weight", "equal weight", "market perform", "sector perform", "sector weight", "perform",
        "in-line", "in line", "peer perform", "tut", "endekse paralel getiri", "nötr", "notr"}
SELL = {"sell", "strong sell", "underweight", "underperform", "market underperform", "sector underperform", "reduce",
        "negative", "sat", "endeksin altında getiri", "endeksin altinda getiri"}
# Headlines that describe an analyst note (vs. conferences, CEO interviews, deal banking).
NOTE_RX = re.compile(r"price target|PT|upgrade|downgrade|initiat|reiterat|maintain|raises|lifts|boosts|cuts|lowers|"
                     r"trims|overweight|underweight|outperform|underperform|top pick|buy|sell|neutral|"
                     r"rating|hedef fiyat|tavsiye|öneri", re.I)
US_EXCH = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BTS"}


def normalize(grade: str | None) -> str | None:
    g = (grade or "").strip().lower()
    if not g:
        return None
    return "Buy" if g in BUY else "Hold" if g in HOLD else "Sell" if g in SELL else None


def last_price(yahoo_sym: str) -> tuple[float | None, str | None]:
    import yfinance as yf
    t = yf.Ticker(yahoo_sym)
    h = t.history(period="5d")
    cur = None
    try:
        cur = t.fast_info.get("currency")
    except Exception:  # noqa: BLE001
        pass
    return (float(h["Close"].iloc[-1]) if not h.empty else None), cur


def discover_us_listing(name: str, primary: str) -> str | None:
    """Find a US listing / ADR of the same company (ASML.AS -> ASML)."""
    first = short_name(name).split()[0].lower()
    try:
        quotes = http("GET", YAHOO_SEARCH_URL, params={"q": short_name(name), "quotesCount": 10, "newsCount": 0}).json().get("quotes", [])
    except Exception:  # noqa: BLE001
        return None
    for q in quotes:
        nm = (q.get("longname") or q.get("shortname") or "").lower()
        if q.get("quoteType") == "EQUITY" and q.get("exchange") in US_EXCH and q.get("symbol") != primary and nm.startswith(first):
            return q["symbol"]
    return None


def yahoo_grades(sym: str, since: datetime):
    import yfinance as yf
    u = yf.Ticker(sym).upgrades_downgrades
    if u is None or u.empty:
        return None
    u = u.sort_index(ascending=False)
    return u


def bank_row(display: str, role: str, firms: list[str], df, since: datetime, price: float | None,
             tcur: str | None, listing: str, rcur: str | None, fx_cross: float | None) -> dict:
    row = {"bank": display, "role": role, "covered": False, "reason": "No coverage (180d)", "history": []}
    if df is None:
        return row
    mine = df[df["Firm"].isin(firms)]
    if mine.empty:
        return row
    recent = mine[mine.index >= since.replace(tzinfo=None)]
    if recent.empty:
        last = mine.index[0]
        row["reason"] = f"No coverage (180d); last action {last:%Y-%m-%d}"
        return row
    hist = []
    for ts, r in recent.iterrows():
        grade = r.get("ToGrade") or r.get("FromGrade") or ""
        hist.append({"date": f"{ts:%Y-%m-%d}", "rating_raw": grade or None, "rating": normalize(grade),
                     "target": float(r["currentPriceTarget"]) if r.get("currentPriceTarget") == r.get("currentPriceTarget") and r.get("currentPriceTarget") else None,
                     "prior_target": float(r["priorPriceTarget"]) if r.get("priorPriceTarget") == r.get("priorPriceTarget") and r.get("priorPriceTarget") else None,
                     "action": r.get("Action"), "pt_action": r.get("priceTargetAction")})
    latest = hist[0]
    # empty grade on a PT-only update -> carry the latest known grade (marked inferred)
    rating_raw, inferred = latest["rating_raw"], False
    if not rating_raw:
        older = next((h["rating_raw"] for h in hist[1:] if h["rating_raw"]), None)
        if older is None:
            full = mine[(mine["ToGrade"] != "")]
            older = full.iloc[0]["ToGrade"] if not full.empty else None
        rating_raw, inferred = older, True
    target = latest["target"] if latest["target"] is not None else next((h["target"] for h in hist if h["target"]), None)
    upside = round((target / price - 1) * 100, 2) if target and price else None
    prev_rating = next((h["rating"] for h in hist[1:] if h["rating"]), None)
    rating = normalize(rating_raw)
    row.update({
        "covered": True, "reason": None, "firm_raw": next(iter(set(mine["Firm"]))), "rating_raw": rating_raw,
        "rating": rating, "rating_inferred": inferred, "target": target, "target_currency": tcur,
        "target_listing": listing, "target_report_ccy": round(target * fx_cross, 2) if target and fx_cross else None,
        "upside_pct": upside, "date": latest["date"], "action": latest["pt_action"] or latest["action"],
        "prior_target": latest["prior_target"],
        "rating_change": (f"{prev_rating} → {rating}" if prev_rating and rating and prev_rating != rating else None),
        "history": hist,
        "source": {"name": "Yahoo Finance upgrades/downgrades", "url": f"https://finance.yahoo.com/quote/{listing}/analysis"},
    })
    if rating is None:
        row["errors"] = [f"unmapped grade '{rating_raw}'"]
    return row


def isyatirim(ticker: str, price: float | None, since: datetime) -> dict:
    """Parse Is Yatirim's public company card: 'Hisse Önerisi AL Son Öneri Tarihi 24.04.2026 Hedef Fiyat 455,00'."""
    from bs4 import BeautifulSoup
    url = LOCAL[0][2].format(ticker=ticker)
    row = {"bank": "İş Yatırım", "role": "local", "covered": False, "reason": "No coverage (180d)", "history": [],
           "research_page": url}
    try:
        txt = BeautifulSoup(http("GET", url).text, "lxml").get_text(" ", strip=True)
    except Exception as e:  # noqa: BLE001
        row["errors"] = [f"Is Yatirim page: {e}"]
        return row
    m = re.search(r"Hisse Önerisi\s+(.+?)\s+Son Öneri Tarihi\s+(\d{2}\.\d{2}\.\d{4})\s+Hedef Fiyat\s+([\d.,]+)", txt)
    if not m:
        row["reason"] = "No recommendation on public company card"
        return row
    grade, d, tgt = m.group(1).strip(), datetime.strptime(m.group(2), "%d.%m.%Y"), float(m.group(3).replace(".", "").replace(",", "."))
    theme = None
    i = txt.find("Yatırım Teması")
    if i >= 0:  # long free text; keep whole sentences up to ~1200 chars
        chunk = txt[i + len("Yatırım Teması"):i + 1300].strip()
        theme = chunk[:chunk.rfind(". ") + 1] if ". " in chunk else chunk
    if d < since.replace(tzinfo=None):
        row["reason"] = f"No coverage (180d); last recommendation {d:%Y-%m-%d}"
        return row
    row.update({"covered": True, "reason": None, "firm_raw": "İş Yatırım", "rating_raw": grade, "rating": normalize(grade),
                "target": tgt, "target_currency": "TRY", "target_listing": ticker, "target_report_ccy": tgt,
                "upside_pct": round((tgt / price - 1) * 100, 2) if price else None, "date": f"{d:%Y-%m-%d}",
                "action": None, "history": [{"date": f"{d:%Y-%m-%d}", "rating_raw": grade, "rating": normalize(grade), "target": tgt}],
                "investment_theme_tr": theme,
                "source": {"name": "İş Yatırım company card (public)", "url": url}})
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--aliases", default="")
    ap.add_argument("--adr", help="US listing / ADR Yahoo symbol to use when the primary has no rating data")
    ap.add_argument("--price", help="price.json (current price of the primary listing)")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--out")
    a = ap.parse_args()
    errors: list = []
    exch, ticker = a.tv.split(":", 1)
    bist = exch == "BIST"
    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    out = {"fetched_at": now_iso(), "window_days": a.days, "tv_symbol": a.tv, "errors": errors}

    # current price + report currency of the primary listing
    price, rcur = None, None
    try:
        if a.price:
            q = load_json(a.price)["quote"]
            price, rcur = q.get("price"), q.get("currency")
        if price is None:
            d = tv_scan([a.tv], ["close", "currency"]).get(a.tv) or {}
            price, rcur = d.get("close"), d.get("currency")
    except Exception as e:  # noqa: BLE001
        errors.append(f"price: {e}")
    out["current_price"], out["price_currency"] = price, rcur

    # structured ratings: primary listing, else US listing / ADR
    df, listing, tcur, lprice = None, a.yahoo, rcur, price
    try:
        df = yahoo_grades(a.yahoo, since)
    except Exception as e:  # noqa: BLE001
        errors.append(f"Yahoo grades {a.yahoo}: {e}")
    if df is None and not bist:
        adr = a.adr or discover_us_listing(a.name, a.yahoo)
        if adr:
            try:
                df = yahoo_grades(adr, since)
                if df is not None:
                    listing = adr
                    lprice, tcur = last_price(adr)
                    out["adr_used"] = {"symbol": adr, "price": lprice, "currency": tcur,
                                       "note": "targets are for the US listing; upside computed vs that listing's price"}
            except Exception as e:  # noqa: BLE001
                errors.append(f"Yahoo grades {adr}: {e}")
    if df is None:
        if bist:  # expected: Yahoo has no grade feed for BIST; local brokers cover it
            out["note"] = f"no Yahoo rating data for {a.yahoo} (expected for BIST)"
        else:
            errors.append(f"no Yahoo rating data for {a.yahoo} or a US listing")
    fx_cross = 1.0
    if tcur and rcur and tcur != rcur:
        t_usd, _ = fx_to_usd(tcur)
        r_usd, _ = fx_to_usd(rcur)
        fx_cross = t_usd / r_usd if t_usd and r_usd else None
    out["target_currency"], out["target_listing"] = tcur, listing

    rows = [bank_row(n, "fixed", firms, df, since, lprice, tcur, listing, rcur, fx_cross) for n, firms, _ in FIXED]
    subs = [bank_row(n, "substitute", firms, df, since, lprice, tcur, listing, rcur, fx_cross) for n, firms, _ in SUBSTITUTES]
    subs = sorted([s for s in subs if s["covered"]], key=lambda s: s["date"], reverse=True)[:3]
    rows += subs
    local_rows = []
    if bist:
        local_rows.append(isyatirim(ticker, price, since))
        for n, _, page in LOCAL[1:]:
            local_rows.append({"bank": n, "role": "local", "covered": None, "reason": "agent: check research page / coverage",
                               "research_page": page, "history": []})

    # press coverage of the notes
    names = list(dict.fromkeys([short_name(a.name)] + [x.strip() for x in a.aliases.split(",") if x.strip()]))
    company = " OR ".join(f'"{n}"' for n in names)
    match = names + ([ticker] if len(ticker) >= 3 and not ticker.isdigit() else [])
    outlets = {**OUTLETS, **FINANCE_PRESS, **(BIST_PRESS if bist else {})}
    groups = {"fixed": FIXED, "substitute": SUBSTITUTES}
    queries = []
    for g, banks in groups.items():
        bank_terms = " OR ".join(f'"{al}"' for _, _, als in banks for al in als[:2])
        queries += [(g, f"({bank_terms}) ({company}) when:{a.days}d site:{dom}") for dom in outlets.values()]
    if bist:
        bank_terms = " OR ".join(f'"{al}"' for _, als, _ in LOCAL for al in als[:2])
        queries += [("local", f"({bank_terms}) ({company}) when:{a.days}d site:{dom}") for dom in outlets.values()]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda q: collect([q], outlets, a.days, errors, match), queries))
    articles = {it["url"]: it for res in results for it in res}.values()
    alias_rx = {n: re.compile("|".join(r"(?<![A-Za-z])" + re.escape(al) + r"(?![A-Za-z])" for al in als), re.I)
                for n, _, als in FIXED + SUBSTITUTES}
    alias_rx.update({n: re.compile("|".join(re.escape(al) for al in als), re.I) for n, als, _ in LOCAL})
    by_bank: dict[str, list] = {}
    for it in sorted(articles, key=lambda x: x.get("date") or "", reverse=True):
        for n, rx in alias_rx.items():
            if rx.search(it["headline"]):
                art = {k: it[k] for k in ("date", "outlet", "headline", "url")}
                art["is_note"] = bool(NOTE_RX.search(it["headline"]))
                by_bank.setdefault(n, []).append(art)
    for r in rows + local_rows:
        arts = by_bank.get(r["bank"], [])
        # analyst-note headlines first, then the rest (newest first inside each group)
        r["coverage_articles"] = ([x for x in arts if x["is_note"]] + [x for x in arts if not x["is_note"]])[:8]
        # GOTCHA: Yahoo's grade feed is incomplete (NVDA: no Goldman row, yet Investing.com
        # reported "Goldman Sachs raises Nvidia stock price target" on 2026-08-27).
        if r["covered"] is False and any(x["is_note"] for x in arts):
            r["press_rating_hint"] = True
            r["reason"] = (r.get("reason") or "No coverage (180d)") +                 "; press reports a rating action in window - agent: verify and fill from the cited article"
        if r["role"] == "local" and r["covered"] is None:
            r["covered"] = None if r["coverage_articles"] else False
    out["banks"] = rows
    out["local_candidates"] = local_rows
    out["coverage_outlets"] = list(outlets)

    covered = [r for r in rows + [l for l in local_rows if l.get("covered") and l.get("rating")] if r["covered"]]
    fixed_cov = [r for r in rows if r["role"] == "fixed" and r["covered"]]

    def counts(rs):
        return {k.lower(): sum(1 for r in rs if r.get("rating") == k) for k in ("Buy", "Hold", "Sell")}
    ups = [r["upside_pct"] for r in covered if r.get("upside_pct") is not None]
    tgts = [r["target_report_ccy"] for r in covered if r.get("target_report_ccy") is not None]
    raises = sum(1 for r in covered for h in r["history"] if (h.get("pt_action") or "").lower() == "raises" or (h.get("action") or "") == "up")
    lowers = sum(1 for r in covered for h in r["history"] if (h.get("pt_action") or "").lower() == "lowers" or (h.get("action") or "") == "down")
    out["summary"] = {**counts(covered), "covered_total": len(covered), "covered_fixed": len(fixed_cov),
                      "fixed": counts(fixed_cov), "median_target_report_ccy": round(statistics.median(tgts), 2) if tgts else None,
                      "median_upside_pct": round(statistics.median(ups), 2) if ups else None,
                      "raises_window": raises, "lowers_window": lowers,
                      "articles_found": sum(len(r["coverage_articles"]) for r in rows + local_rows)}
    write_json(a.out, out)


if __name__ == "__main__":
    main()
