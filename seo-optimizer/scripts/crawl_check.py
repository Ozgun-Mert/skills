"""Crawl a site the way a crawler's first pass sees it: raw HTML, no JavaScript, no auto-redirects.

Checks per page: HTTP status, redirect chains/loops, title, meta description, meta robots,
X-Robots-Tag, canonical, <html lang>, H1 count, images without alt, JSON-LD types, hreflang,
word count of the raw HTML, leftover {{PLACEHOLDER: ...}} markers. Site-wide: duplicate titles /
descriptions, click depth from the home page, orphan pages (in sitemap but never linked),
soft-404 probe.

Usage:
  python crawl_check.py http://localhost:3000 [--sitemap] [--max-pages 200] [--out seo/crawl.json]
Standard library only. Prints a JSON report (pages[], issues[], summary).
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from collections import deque
from html.parser import HTMLParser
from urllib import error, parse, request

UA = "Mozilla/5.0 (compatible; optimize-seo-crawl/1.0)"
SKIP_EXT = re.compile(r"\.(png|jpe?g|gif|webp|avif|svg|ico|pdf|zip|mp4|webm|mp3|css|js|mjs|json|xml|txt|woff2?|ttf|map)$", re.I)
PLACEHOLDER = re.compile(r"\{\{PLACEHOLDER:\s*([a-zA-Z0-9_]+)\s*\}\}")


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = request.build_opener(NoRedirect)


def fetch_once(url, timeout=20):
    req = request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"})
    try:
        r = OPENER.open(req, timeout=timeout)
        code, headers, body = r.status, r.headers, r.read(3_000_000)
    except error.HTTPError as e:
        code, headers = e.code, e.headers
        try:
            body = e.read(3_000_000)
        except Exception:
            body = b""
    except Exception as e:  # connection refused, DNS, timeout
        return {"status": None, "error": str(e)[:200], "headers": {}, "body": b""}
    if headers.get("Content-Encoding") == "gzip":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    return {"status": code, "headers": headers, "body": body}


def fetch(url, max_hops=10):
    chain, seen, cur = [], set(), url
    while True:
        r = fetch_once(cur)
        if r["status"] in (301, 302, 303, 307, 308):
            loc = r["headers"].get("Location")
            chain.append({"url": cur, "status": r["status"], "location": loc})
            if not loc:
                break
            nxt = parse.urljoin(cur, loc)
            if nxt in seen or len(chain) > max_hops:
                r["loop"] = True
                break
            seen.add(cur)
            cur = nxt
            continue
        break
    r["chain"], r["final_url"] = chain, cur
    return r


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title = "", False
        self.meta, self.links, self.imgs, self.h1, self.hreflang = {}, [], [], [], []
        self.canonical, self.lang, self.jsonld = None, None, []
        self._skip, self._h1, self._ld = 0, None, None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            n = (a.get("name") or a.get("property") or "").lower()
            if n:
                self.meta[n] = a.get("content", "")
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel:
                self.canonical = a.get("href")
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang.append({"hreflang": a["hreflang"], "href": a.get("href")})
        elif tag == "a" and "href" in a:
            self.links.append({"href": a["href"], "rel": a.get("rel", "")})
        elif tag == "img":
            self.imgs.append({"src": a.get("src", "")[:200], "has_alt": "alt" in a, "alt": a.get("alt")})
        elif tag == "h1":
            self._h1 = []
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._ld = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "h1" and self._h1 is not None:
            self.h1.append(re.sub(r"\s+", " ", "".join(self._h1)).strip())
            self._h1 = None
        elif tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            if tag == "script" and self._ld is not None:
                self.jsonld.append("".join(self._ld))
                self._ld = None

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
            return
        if self.in_title:
            self.title += data
        if self._h1 is not None:
            self._h1.append(data)
        if not self._skip:
            self.text.append(data)


def jsonld_types(blocks):
    types = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("@type")
            if t:
                types.extend(t if isinstance(t, list) else [t])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    errors = 0
    for b in blocks:
        try:
            walk(json.loads(b))
        except json.JSONDecodeError:
            errors += 1
    return sorted(set(types)), errors


def norm(u):
    p = parse.urlsplit(u)
    path = p.path or "/"
    return parse.urlunsplit((p.scheme, p.netloc.lower(), path, p.query, ""))


def sitemap_urls(base):
    urls, todo, seen = [], [parse.urljoin(base, "/sitemap.xml")], set()
    rb = fetch_once(parse.urljoin(base, "/robots.txt"))
    if rb["status"] == 200:
        for line in rb["body"].decode("utf-8", "replace").splitlines():
            if line.lower().startswith("sitemap:"):
                todo.append(line.split(":", 1)[1].strip())
    while todo:
        sm = todo.pop()
        if sm in seen:
            continue
        seen.add(sm)
        sm_local = to_base_host(sm, base)
        r = fetch_once(sm_local)
        if r["status"] != 200:
            continue
        try:
            root = ET.fromstring(r["body"])
        except ET.ParseError:
            continue
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        for loc in root.iter(ns + "loc"):
            u = (loc.text or "").strip()
            if root.tag == ns + "sitemapindex":
                todo.append(u)
            else:
                urls.append(u)
    return urls


def to_base_host(u, base):
    """Rewrite a production URL onto the crawl host (e.g. sitemap built for example.com, crawl on localhost)."""
    pb, pu = parse.urlsplit(base), parse.urlsplit(u)
    if pu.netloc and pu.netloc != pb.netloc:
        return parse.urlunsplit((pb.scheme, pb.netloc, pu.path or "/", pu.query, ""))
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--sitemap", action="store_true", help="also seed from sitemap.xml / robots.txt Sitemap:")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--out")
    a = ap.parse_args()
    base = a.base.rstrip("/") + "/"
    host = parse.urlsplit(base).netloc

    pages, issues = {}, []
    depth, inlinks = {norm(base): 0}, {}
    queue = deque([norm(base)])
    sm_urls = []
    if a.sitemap:
        sm_urls = [norm(to_base_host(u, base)) for u in sitemap_urls(base)]

    def add_issue(t, url=None, **kw):
        issues.append({"type": t, "url": url, **kw})

    while queue and len(pages) < a.max_pages:
        url = queue.popleft()
        if url in pages:
            continue
        r = fetch(url)
        if a.delay:
            time.sleep(a.delay)
        pg = {"url": url, "status": r["status"], "depth": depth.get(url)}
        if r.get("error"):
            pg["error"] = r["error"]
            add_issue("fetch_error", url, detail=r["error"])
            pages[url] = pg
            continue
        if r["chain"]:
            pg["redirects"] = r["chain"]
            pg["final_url"] = r["final_url"]
            if r.get("loop"):
                add_issue("redirect_loop", url)
            elif len(r["chain"]) > 1:
                add_issue("redirect_chain", url, hops=len(r["chain"]))
            if any(h["status"] in (302, 307) for h in r["chain"]):
                add_issue("temporary_redirect", url, detail="302/307 used; use 301/308 for permanent moves")
        st = r["status"]
        if st and st >= 500:
            add_issue("status_5xx", url, status=st)
        elif st and st >= 400:
            add_issue("status_4xx_linked" if inlinks.get(url) else "status_4xx", url, status=st,
                      linked_from=inlinks.get(url, [])[:5])
        xrt = (r["headers"].get("X-Robots-Tag") or "") if r["headers"] else ""
        ctype = (r["headers"].get("Content-Type") or "") if r["headers"] else ""
        if st == 200 and "html" in ctype:
            html = r["body"].decode("utf-8", "replace")
            p = PageParser()
            try:
                p.feed(html)
            except Exception:
                pass
            words = len(re.findall(r"\w+", " ".join(p.text), re.U))
            robots_meta = (p.meta.get("robots", "") + "," + p.meta.get("googlebot", "") + "," + xrt).lower()
            types, ld_err = jsonld_types(p.jsonld)
            pg.update({
                "title": re.sub(r"\s+", " ", p.title).strip(),
                "description": p.meta.get("description"),
                "robots": robots_meta.strip(","),
                "noindex": "noindex" in robots_meta,
                "canonical": p.canonical,
                "lang": p.lang,
                "h1": p.h1,
                "word_count": words,
                "img_total": len(p.imgs),
                "img_missing_alt": [i["src"] for i in p.imgs if not i["has_alt"]][:20],
                "jsonld_types": types,
                "hreflang": p.hreflang,
                "og_title": p.meta.get("og:title"),
                "placeholders": sorted(set(PLACEHOLDER.findall(html))),
            })
            if ld_err:
                add_issue("jsonld_invalid", url, blocks=ld_err)
            if not pg["title"]:
                add_issue("missing_title", url)
            elif not 15 <= len(pg["title"]) <= 65:
                add_issue("title_length", url, length=len(pg["title"]))
            if not pg["description"]:
                add_issue("missing_description", url)
            if len(p.h1) != 1:
                add_issue("h1_count", url, count=len(p.h1))
            if not p.lang:
                add_issue("missing_html_lang", url)
            if not p.canonical:
                add_issue("missing_canonical", url)
            else:
                c = norm(parse.urljoin(url, p.canonical))
                c_local = norm(to_base_host(c, base))
                if c_local != norm(r["final_url"]) and not pg["noindex"]:
                    add_issue("canonical_mismatch", url, canonical=p.canonical)
            if pg["img_missing_alt"]:
                add_issue("img_missing_alt", url, count=len(pg["img_missing_alt"]))
            if pg["placeholders"]:
                add_issue("placeholder_left", url, names=pg["placeholders"])
            if words < 120 and not pg["noindex"]:
                add_issue("thin_html", url, words=words,
                          detail="Little text in raw HTML: content may be rendered client-side, or the page is thin.")
            for l in p.links:
                href = l["href"].strip()
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "sms:", "whatsapp:")):
                    continue
                absu = norm(parse.urljoin(r["final_url"], href))
                if parse.urlsplit(absu).netloc != host or SKIP_EXT.search(parse.urlsplit(absu).path):
                    continue
                inlinks.setdefault(absu, [])
                if url not in inlinks[absu]:
                    inlinks[absu].append(url)
                if absu not in depth:
                    depth[absu] = (depth.get(url) or 0) + 1
                if absu not in pages and absu not in queue:
                    queue.append(absu)
        pages[url] = pg
        # After the link graph is exhausted, add sitemap URLs nobody linked to (orphan candidates).
        if not queue and sm_urls:
            queue.extend(u for u in sm_urls if u not in pages)
            sm_urls = []

    # Site-wide checks
    idx_pages = [p for p in pages.values() if p.get("status") == 200 and "title" in p and not p.get("noindex")]
    for field, t in (("title", "duplicate_title"), ("description", "duplicate_description")):
        seen = {}
        for p in idx_pages:
            v = (p.get(field) or "").strip()
            if v:
                seen.setdefault(v, []).append(p["url"])
        for v, us in seen.items():
            if len(us) > 1:
                add_issue(t, None, value=v[:120], urls=us)
    home = norm(base)
    for u, p in pages.items():
        p["inlinks"] = len(inlinks.get(u, []))
        p["depth"] = depth.get(u)
        if u != home and p.get("status") == 200 and not inlinks.get(u):
            add_issue("orphan", u, detail="Reachable only via sitemap/direct URL; no internal link points here.")
        if (p.get("depth") or 0) > 3 and p.get("status") == 200:
            add_issue("deep_page", u, depth=p["depth"])

    # Soft-404 probe
    probe = parse.urljoin(base, f"/optimize-seo-404-probe-{uuid.uuid4().hex[:8]}")
    pr = fetch(probe)
    soft = {"probe_url": probe, "status": pr["status"], "redirects": pr["chain"]}
    if pr["status"] == 200:
        add_issue("soft_404", probe, detail="Unknown URL returns 200; should return 404/410.")

    counts = {}
    for i in issues:
        counts[i["type"]] = counts.get(i["type"], 0) + 1
    out = {
        "base": base,
        "crawled": len(pages),
        "summary": {"issue_counts": counts,
                    "status_counts": {str(k): sum(1 for p in pages.values() if p.get("status") == k)
                                      for k in sorted({p.get("status") for p in pages.values()}, key=lambda x: (x is None, x))}},
        "soft_404_probe": soft,
        "issues": issues,
        "pages": list(pages.values()),
    }
    s = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(s)
    print(s)


if __name__ == "__main__":
    sys.exit(main())
