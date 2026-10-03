"""Tier-1 news fetcher (Bloomberg, Reuters, FT, WSJ, CNBC) + official company disclosures.

Stock mode:
  python fetch_news.py --name "Turk Hava Yollari" --ticker THYAO --aliases "Turkish Airlines,THY" \
      [--exchange BIST] [--cik 320193] [--days 30] [--out data/THYAO/news.json]
World mode (Phase 1 world-news mapper):
  python fetch_news.py --world [--topics "Iran,tariffs,..."] [--days 14] [--out world-news-raw.json]

Method: Google News RSS restricted with site: per outlet; results whose <source> is not on
the whitelist are dropped. URLs are Google News redirect links that open the original article.
"""
from __future__ import annotations

import argparse
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from common import http, now_iso, write_json

OUTLETS = {
    "Bloomberg": "bloomberg.com", "Reuters": "reuters.com", "Financial Times": "ft.com",
    "Wall Street Journal": "wsj.com", "CNBC": "cnbc.com",
}
OFFICIAL = {"KAP": "kap.org.tr"}
# topic -> (Google query, headline keywords that must appear)
WORLD_TOPICS = {
    "Wars & conflicts": ("war OR strike OR ceasefire OR missile", ["war", "strike", "ceasefire", "missile", "troops", "invasion", "attack"]),
    "Iran": ("Iran", ["Iran", "Tehran", "Hormuz"]),
    "Israel / Middle East": ("Israel OR Gaza OR Lebanon OR Houthi", ["Israel", "Gaza", "Lebanon", "Houthi", "Red Sea", "Hezbollah"]),
    "Russia-Ukraine": ("Russia Ukraine", ["Russia", "Ukraine", "Kremlin", "Putin", "Zelenskiy", "Zelensky"]),
    "China-Taiwan / US-China": ("China Taiwan OR Beijing Washington", ["Taiwan", "Beijing", "China"]),
    "Tariffs & trade": ("tariffs OR trade war OR trade deal", ["tariff", "trade war", "trade deal", "duties", "import"]),
    "Sanctions": ("sanctions", ["sanction"]),
    "Fed / US rates": ("Federal Reserve rates", ["Fed", "Federal Reserve", "Powell", "rate cut", "rate hike", "Treasury yields"]),
    "ECB / Europe rates": ("ECB rates", ["ECB", "Lagarde", "euro zone", "eurozone"]),
    "Oil & energy": ("oil prices OPEC", ["oil", "OPEC", "crude", "Brent", "gas prices", "LNG"]),
    "Chip export controls": ("semiconductor export controls", ["chip", "semiconductor", "export control", "Nvidia", "TSMC"]),
    "Elections & politics": ("election markets", ["election", "vote", "shutdown", "Congress", "parliament"]),
    "Growth / recession": ("recession OR slowdown OR GDP", ["recession", "slowdown", "GDP", "jobs report", "payrolls", "inflation", "CPI"]),
    "Turkey macro": ("Turkey central bank lira", ["Turkey", "Turkish", "lira", "Erdogan", "TCMB"]),
    "China economy": ("China economy stimulus", ["China", "Chinese", "yuan", "PBOC"]),
    "Supply chains": ("supply chain disruption", ["supply chain", "shortage", "shipping", "port", "Suez", "Panama"]),
    "FX / dollar": ("dollar currency markets", ["dollar", "yen", "euro", "currency", "FX"]),
}
WORLD_CAP_PER_TOPIC = 25
SUFFIXES = re.compile(r"\b(inc|corp|corporation|co|ltd|plc|ag|sa|nv|se|a\.?o\.?|a\.?s\.?|holding|holdings|group|company|limited|class [abc])\.?$", re.I)


def short_name(name: str) -> str:
    n = name.replace(",", " ").strip()
    for _ in range(3):
        n = SUFFIXES.sub("", n).strip(" .")
    return n


def gnews(query: str) -> list[dict]:
    r = http("GET", "https://news.google.com/rss/search",
             params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    import feedparser
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries:
        src = getattr(e, "source", None) or {}
        src_url = src.get("href", "") if isinstance(src, dict) else ""
        title = e.get("title", "")
        outlet = src.get("title") if isinstance(src, dict) else None
        if outlet and title.endswith(" - " + outlet):
            title = title[: -len(" - " + outlet)]
        try:
            dt = parsedate_to_datetime(e.get("published"))
        except Exception:  # noqa: BLE001
            dt = None
        desc = html.unescape(re.sub(r"<[^>]+>", " ", e.get("summary", ""))).strip()
        items.append({"date": dt.strftime("%Y-%m-%d") if dt else None, "_dt": dt, "outlet": outlet,
                      "source_url": src_url, "headline": title.strip(), "url": e.get("link"),
                      "snippet": re.sub(r"\s+", " ", desc)[:300]})
    return items


def allowed(item: dict, domains: dict) -> str | None:
    for name, dom in domains.items():
        if dom in (item.get("source_url") or "") or (item.get("outlet") or "").lower().startswith(name.lower()[:8]):
            return name
    return None


def collect(queries: list[tuple[str, str]], domains: dict, days: int, errors: list,
            must_match: list[str] | None = None) -> list[dict]:
    # GOTCHA: Google News matches article *bodies*, so "Apple" returns hundreds of unrelated
    # CNBC/WSJ items. In stock mode keep only items whose headline names the company.
    pat = re.compile("|".join(r"(?<![A-Za-z0-9])" + re.escape(m) + r"(?![A-Za-z0-9])" for m in must_match), re.I) if must_match else None
    seen, out = set(), []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for tag, q in queries:
        try:
            for it in gnews(q):
                name = allowed(it, domains)
                if not name or (it["_dt"] and it["_dt"] < cutoff):
                    continue
                if pat and not pat.search(it["headline"]):
                    continue
                key = re.sub(r"[^a-z0-9]", "", it["headline"].lower())[:70]
                if key in seen:
                    continue
                seen.add(key)
                it["outlet"] = name
                it["topic"] = tag
                out.append(it)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{q}: {e}")
    out.sort(key=lambda x: x["_dt"] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    for it in out:
        it.pop("_dt", None)
    return out


def edgar_8k(cik: str, days: int, errors: list) -> list[dict]:
    try:
        cik10 = str(int(cik)).zfill(10)
        j = http("GET", f"https://data.sec.gov/submissions/CIK{cik10}.json", sec=True).json()
        rec = j["filings"]["recent"]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        out = []
        for form, d, acc, doc, items in zip(rec["form"], rec["filingDate"], rec["accessionNumber"],
                                            rec["primaryDocument"], rec.get("items", [""] * len(rec["form"]))):
            if d < cutoff:
                break
            if form in ("8-K", "6-K", "10-Q", "10-K", "SC 13D", "4") and form != "4":
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
                out.append({"date": d, "outlet": "SEC EDGAR", "headline": f"{form} filed" + (f" (items {items})" if items else ""),
                            "url": url, "form": form})
        return out
    except Exception as e:  # noqa: BLE001
        errors.append(f"EDGAR submissions: {e}")
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--ticker")
    ap.add_argument("--aliases", default="", help="comma-separated extra names used by the press")
    ap.add_argument("--exchange", default="")
    ap.add_argument("--cik")
    ap.add_argument("--world", action="store_true")
    ap.add_argument("--topics", help="comma-separated world topics (overrides defaults)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--loose", action="store_true", help="stock mode: keep items even if headline lacks the name")
    ap.add_argument("--out")
    a = ap.parse_args()
    errors: list = []
    out = {"fetched_at": now_iso(), "days": a.days, "outlet_whitelist": list(OUTLETS),
           "method": "Google News RSS with site: filter per outlet; non-whitelisted sources dropped",
           "errors": errors}
    if a.world:
        topics = ({t.strip(): (t.strip(), [t.strip()]) for t in a.topics.split(",")} if a.topics else WORLD_TOPICS)
        items = []
        for tag, (q, kws) in topics.items():
            qs = [(tag, f"({q}) when:{a.days}d site:{dom}") for dom in OUTLETS.values()]
            items += collect(qs, OUTLETS, a.days, errors, kws)[:WORLD_CAP_PER_TOPIC]
        out["mode"] = "world"
        out["items"] = items
    else:
        if not a.name:
            ap.error("--name is required in stock mode")
        names = [short_name(a.name)] + [x.strip() for x in a.aliases.split(",") if x.strip()]
        names = list(dict.fromkeys(names))
        term = " OR ".join(f'"{n}"' for n in names)
        if a.ticker and len(a.ticker) >= 3 and not a.ticker.isdigit():
            term += f' OR "{a.ticker} stock"'
        qs = [(n, f"({term}) when:{a.days}d site:{dom}") for n, dom in OUTLETS.items()]
        out["mode"] = "stock"
        out["query_names"] = names
        match = None if a.loose else names + ([a.ticker] if a.ticker and not a.ticker.isdigit() else [])
        out["items"] = collect(qs, OUTLETS, a.days, errors, match)
        official = []
        if a.cik:
            official += edgar_8k(a.cik, a.days, errors)
        if a.exchange.upper() == "BIST":
            official += collect([("KAP", f"({term}) when:{a.days}d site:kap.org.tr")], OFFICIAL, a.days, errors, match)
        out["official"] = official
    out["count"] = len(out["items"])
    if out["count"] == 0:
        errors.append("no tier-1 items found - widen --days or add --aliases (press name of the company)")
    write_json(a.out, out)


if __name__ == "__main__":
    main()
