"""Validate robots.txt and sitemap.xml for a site, optionally cross-checked with crawl_check.py output.

robots.txt: exists (200, text), has a Sitemap: line, does not block CSS/JS/framework asset paths,
does not block URLs listed in the sitemap.
sitemap.xml (and sitemap indexes): well-formed XML, absolute https URLs, single host, no duplicates,
valid W3C lastmod, lastmod not identical everywhere, every URL returns 200 (no redirects), not
noindex, canonical == loc, under 50,000 URLs. With --crawl: indexable crawled pages missing from
the sitemap.

Usage:
  python sitemap_check.py http://localhost:3000 [--crawl seo/crawl.json] [--no-fetch-urls] [--out file]
When run against localhost while the sitemap lists the production host, URLs are fetched on the
local host (path preserved) and the host mismatch is reported as info, not an error.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib import error, parse, request, robotparser

UA = "Mozilla/5.0 (compatible; optimize-seo-crawl/1.0)"
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
W3C = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?)?)?$")
ASSET_PATHS = ["/_next/static/x.js", "/_next/static/x.css", "/assets/x.js", "/assets/x.css",
               "/static/x.js", "/static/x.css", "/x.css", "/x.js", "/_nuxt/x.js", "/_astro/x.css", "/build/x.js"]


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = request.build_opener(NoRedirect)


def get(url):
    req = request.Request(url, headers={"User-Agent": UA})
    try:
        r = OPENER.open(req, timeout=20)
        return r.status, r.headers, r.read(10_000_000)
    except error.HTTPError as e:
        return e.code, e.headers, b""
    except Exception as e:
        return None, {}, str(e).encode()


def local(u, base):
    pb, pu = parse.urlsplit(base), parse.urlsplit(u)
    return parse.urlunsplit((pb.scheme, pb.netloc, pu.path or "/", pu.query, "")) if pu.netloc else u


def norm(u):
    p = parse.urlsplit(u)
    return parse.urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--crawl")
    ap.add_argument("--no-fetch-urls", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    base = a.base.rstrip("/") + "/"
    issues, info = [], []

    def issue(t, **kw):
        issues.append({"type": t, **kw})

    # robots.txt
    robots_url = parse.urljoin(base, "/robots.txt")
    st, hd, body = get(robots_url)
    robots = {"url": robots_url, "status": st, "sitemaps": []}
    rp = robotparser.RobotFileParser()
    if st == 200:
        text = body.decode("utf-8", "replace")
        robots["content"] = text[:4000]
        rp.parse(text.splitlines())
        robots["sitemaps"] = [l.split(":", 1)[1].strip() for l in text.splitlines() if l.lower().startswith("sitemap:")]
        if not robots["sitemaps"]:
            issue("robots_no_sitemap_line")
        blocked_assets = [p for p in ASSET_PATHS if not rp.can_fetch("Googlebot", parse.urljoin(base, p))]
        if blocked_assets:
            issue("robots_blocks_assets", paths=blocked_assets)
        if not rp.can_fetch("Googlebot", base):
            issue("robots_blocks_home", detail="Disallow covers the home page. Is the whole site blocked?")
    else:
        issue("robots_missing", status=st)
        rp = None

    # sitemaps
    todo = [local(s, base) for s in robots["sitemaps"]] or [parse.urljoin(base, "/sitemap.xml")]
    if parse.urljoin(base, "/sitemap.xml") not in todo:
        todo.append(parse.urljoin(base, "/sitemap.xml"))
    seen, entries, sitemaps = set(), [], []
    while todo:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        st, hd, body = get(sm)
        rec = {"url": sm, "status": st}
        sitemaps.append(rec)
        if st != 200:
            if sm.endswith("/sitemap.xml") and not entries:
                issue("sitemap_missing", url=sm, status=st)
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            issue("sitemap_invalid_xml", url=sm, detail=str(e))
            continue
        if root.tag == NS + "sitemapindex":
            rec["type"] = "index"
            for loc in root.iter(NS + "loc"):
                todo.append(local((loc.text or "").strip(), base))
            continue
        if root.tag != NS + "urlset":
            issue("sitemap_wrong_namespace", url=sm, tag=root.tag)
            continue
        rec["type"] = "urlset"
        for u in root.findall(NS + "url"):
            loc = (u.findtext(NS + "loc") or "").strip()
            lm = (u.findtext(NS + "lastmod") or "").strip()
            entries.append({"loc": loc, "lastmod": lm or None, "sitemap": sm})
        rec["count"] = len(root.findall(NS + "url"))
        if rec["count"] > 50000:
            issue("sitemap_too_large", url=sm, count=rec["count"])

    locs = [e["loc"] for e in entries]
    hosts = sorted({parse.urlsplit(l).netloc for l in locs if parse.urlsplit(l).netloc})
    if len(hosts) > 1:
        issue("sitemap_multiple_hosts", hosts=hosts)
    if hosts and hosts[0] != parse.urlsplit(base).netloc:
        info.append(f"Sitemap host {hosts[0]} differs from checked host; URLs fetched on {parse.urlsplit(base).netloc}.")
    for l in locs:
        p = parse.urlsplit(l)
        if not p.scheme or not p.netloc:
            issue("sitemap_relative_loc", loc=l)
        elif p.scheme != "https" and not p.netloc.startswith(("localhost", "127.0.0.1")):
            issue("sitemap_http_loc", loc=l)
        if "{{PLACEHOLDER" in l or "PLACEHOLDER" in l:
            issue("sitemap_placeholder_host", loc=l)
    dups = sorted({l for l in locs if locs.count(l) > 1})
    if dups:
        issue("sitemap_duplicate_loc", locs=dups)
    lms = [e["lastmod"] for e in entries]
    bad_lm = [e["loc"] for e in entries if e["lastmod"] and not W3C.match(e["lastmod"])]
    if bad_lm:
        issue("sitemap_bad_lastmod", locs=bad_lm[:20])
    if not any(lms) and entries:
        issue("sitemap_no_lastmod")
    elif len(entries) > 3 and len(set(lms)) == 1:
        issue("sitemap_lastmod_all_identical", value=lms[0],
              detail="Every URL has the same lastmod. Fine if every page really changed that day (e.g. a first "
                     "optimize-seo run); a problem if it is 'now' at every build, which Google ignores.")

    crawl_pages = {}
    if a.crawl and os.path.exists(a.crawl):
        with open(a.crawl, encoding="utf-8") as f:
            crawl_pages = {norm(p["url"]): p for p in json.load(f).get("pages", [])}

    if not a.no_fetch_urls:
        for e in entries[:2000]:
            lu = norm(local(e["loc"], base))
            p = crawl_pages.get(lu)
            if p is None:
                st, hd, body = get(lu)
                p = {"status": st}
                if st == 200:
                    html = body.decode("utf-8", "replace")
                    m = re.search(r"<link[^>]+rel=[\"']canonical[\"'][^>]*>", html, re.I)
                    if m:
                        h = re.search(r"href=[\"']([^\"']+)", m.group(0))
                        p["canonical"] = h.group(1) if h else None
                    p["noindex"] = bool(re.search(r"<meta[^>]+name=[\"'](robots|googlebot)[\"'][^>]+noindex", html, re.I)) \
                        or "noindex" in (hd.get("X-Robots-Tag") or "").lower()
            e["status"] = p.get("status")
            if p.get("status") != 200:
                issue("sitemap_url_not_200", loc=e["loc"], status=p.get("status"),
                      detail="Sitemaps should list only final 200 URLs (no redirects or errors).")
            if p.get("noindex"):
                issue("noindex_in_sitemap", loc=e["loc"])
            c = p.get("canonical")
            if c and norm(local(parse.urljoin(lu, c), base)) != lu:
                issue("sitemap_loc_not_canonical", loc=e["loc"], canonical=c)
            if rp is not None and not rp.can_fetch("Googlebot", lu):
                issue("robots_blocks_sitemap_url", loc=e["loc"])

    if crawl_pages:
        in_sm = {norm(local(l, base)) for l in locs}
        missing = [u for u, p in crawl_pages.items()
                   if p.get("status") == 200 and p.get("title") is not None and not p.get("noindex") and u not in in_sm
                   and (not p.get("canonical") or norm(local(parse.urljoin(u, p["canonical"]), base)) == u)]
        if missing:
            issue("indexable_page_missing_from_sitemap", urls=missing[:50])

    counts = {}
    for i in issues:
        counts[i["type"]] = counts.get(i["type"], 0) + 1
    out = {"base": base, "robots": robots, "sitemaps": sitemaps, "url_count": len(entries),
           "issue_counts": counts, "issues": issues, "info": info, "entries": entries[:500]}
    s = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(s)
    print(s)


if __name__ == "__main__":
    sys.exit(main())
