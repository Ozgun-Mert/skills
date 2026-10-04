"""PageSpeed Insights (mobile + desktop) for a deployed URL, summarized against Core Web Vitals targets.

Field data (Chrome UX Report, real users, p75) is used when available, first for the URL, then
for the whole origin. Otherwise lab data (Lighthouse) is used, and INP (which lab tests can't
measure) is replaced by Total Blocking Time as a proxy. Output always says which source was used.

Targets: LCP < 2500 ms, INP < 200 ms, CLS < 0.1.

Usage:
  python psi.py https://example.com/page [--key KEY | env PSI_API_KEY] [--strategy mobile desktop] [--out file]
"""
import argparse
import json
import os
import sys
import time
from urllib import error, parse, request

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TARGET = {"LCP": 2500, "INP": 200, "CLS": 0.1}


def call(url, strategy, key):
    q = {"url": url, "strategy": strategy, "category": "performance"}
    if key:
        q["key"] = key
    full = API + "?" + parse.urlencode(q)
    for attempt in range(3):
        try:
            with request.urlopen(request.Request(full, headers={"User-Agent": "optimize-seo/1.0"}), timeout=120) as r:
                return json.load(r), None
        except error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            # "Queries per day" = the shared keyless quota is gone; retrying won't help.
            if e.code == 429 and attempt < 2 and "per day" not in body:
                time.sleep(15 * (attempt + 1))
                continue
            return None, f"HTTP {e.code}: {body}"
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return None, str(e)
    return None, "failed"


def field(le):
    if not le or not le.get("metrics"):
        return None
    m = le["metrics"]
    g = lambda k: (m.get(k) or {}).get("percentile")
    cls = g("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    return {"LCP": g("LARGEST_CONTENTFUL_PAINT_MS"), "INP": g("INTERACTION_TO_NEXT_PAINT"),
            "CLS": (cls / 100.0) if cls is not None else None, "overall": le.get("overall_category")}


def summarize(data, strategy):
    res = {"strategy": strategy}
    f = field(data.get("loadingExperience"))
    src = "field-url"
    if not f or f.get("LCP") is None:
        f = field(data.get("originLoadingExperience"))
        src = "field-origin"
    lh = data.get("lighthouseResult", {})
    au = lh.get("audits", {})
    num = lambda k: (au.get(k) or {}).get("numericValue")
    lab = {"LCP": num("largest-contentful-paint"), "CLS": num("cumulative-layout-shift"),
           "TBT": num("total-blocking-time"), "FCP": num("first-contentful-paint"),
           "SpeedIndex": num("speed-index"),
           "performance_score": round(((lh.get("categories", {}).get("performance") or {}).get("score") or 0) * 100)}
    res["lab"] = lab
    if f and f.get("LCP") is not None:
        res["source"] = src
        res["metrics"] = {"LCP_ms": f["LCP"], "INP_ms": f["INP"], "CLS": f["CLS"]}
        res["pass"] = {
            "LCP": f["LCP"] is not None and f["LCP"] < TARGET["LCP"],
            "INP": None if f["INP"] is None else f["INP"] < TARGET["INP"],
            "CLS": None if f["CLS"] is None else f["CLS"] < TARGET["CLS"],
        }
    else:
        res["source"] = "lab"
        res["metrics"] = {"LCP_ms": lab["LCP"], "INP_ms": None, "TBT_ms_as_INP_proxy": lab["TBT"], "CLS": lab["CLS"]}
        res["pass"] = {
            "LCP": lab["LCP"] is not None and lab["LCP"] < TARGET["LCP"],
            "INP": None if lab["TBT"] is None else lab["TBT"] < 200,
            "CLS": lab["CLS"] is not None and lab["CLS"] < TARGET["CLS"],
        }
        res["note"] = "No field data (not enough real-user traffic). INP judged by lab TBT proxy."
    # Main causes: top opportunities + LCP element + layout shift elements
    opps = []
    for k, v in au.items():
        d = v.get("details") or {}
        if d.get("type") == "opportunity" and (d.get("overallSavingsMs") or 0) >= 100:
            opps.append({"id": k, "title": v.get("title"), "savings_ms": round(d["overallSavingsMs"])})
    res["opportunities"] = sorted(opps, key=lambda x: -x["savings_ms"])[:8]
    lcp_el = (au.get("largest-contentful-paint-element") or {}).get("details", {})
    try:
        items = lcp_el.get("items", [])
        node = items[0].get("items", [{}])[0].get("node") if items and "items" in items[0] else items[0].get("node")
        res["lcp_element"] = (node or {}).get("snippet")
    except (IndexError, AttributeError, TypeError):
        pass
    shifts = (au.get("layout-shifts") or au.get("layout-shift-elements") or {}).get("details", {}).get("items", [])
    res["layout_shift_elements"] = [((i.get("node") or {}).get("snippet") or "")[:160] for i in shifts[:5]]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--key", default=os.environ.get("PSI_API_KEY"))
    ap.add_argument("--strategy", nargs="+", default=["mobile", "desktop"])
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"url": a.url, "targets": {"LCP_ms": 2500, "INP_ms": 200, "CLS": 0.1}, "results": [], "errors": []}
    if not a.url.startswith(("http://", "https://")) or any(h in a.url for h in ("localhost", "127.0.0.1")):
        out["errors"].append("PageSpeed Insights needs a publicly reachable URL; localhost can't be tested.")
    else:
        for s in a.strategy:
            data, err = call(a.url, s, a.key)
            if err:
                hint = None
                if "429" in err:
                    hint = ("Rate limited. The keyless quota is shared by everyone and is often used up. Ask the user for "
                            "a free API key (https://developers.google.com/speed/docs/insights/v5/get-started) and pass "
                            "--key or set PSI_API_KEY, or ask them to run https://pagespeed.web.dev/ and paste the numbers.")
                out["errors"].append({"strategy": s, "error": err[:300], "hint": hint})
                continue
            out["results"].append(summarize(data, s))
    s = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(s)
    print(s)


if __name__ == "__main__":
    sys.exit(main())
