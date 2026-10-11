"""Raw-HTML SEO check of a running frontend: what a crawler sees on its first pass (no JavaScript).

Per page: status, redirects, title, meta description, viewport, robots meta / X-Robots-Tag,
canonical, <html lang>, H1 count, Open Graph, images without alt, JSON-LD validity, raw-HTML word
count, leftover {{PLACEHOLDER: …}}. Site-wide: robots.txt (exists, not blocking everything,
Sitemap: line), sitemap.xml (exists, every URL returns 200, none noindex), duplicate titles and
descriptions, orphans, click depth, soft-404 probe. Pages that redirect to a login page are
treated as private and skipped.

Usage: python seo_check.py http://localhost:3000 [--sitemap] [--max-pages 150] [--root .]
Prints "<n> critical, <n> high, <n> medium, <n> low" plus the top issues; full JSON goes to
<root>/mnm/seo-check.json. Standard library only.
"""
import argparse
import gzip
import json
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from collections import deque
from html.parser import HTMLParser
from urllib import error, parse, request

UA = "Mozilla/5.0 (compatible; make-no-mistakes-seo-check/1.0)"
SKIP_EXT = re.compile(r"\.(png|jpe?g|gif|webp|avif|svg|ico|pdf|zip|mp4|webm|mp3|css|js|mjs|json|xml|txt|woff2?|ttf|map)$", re.I)
PLACEHOLDER = re.compile(r"\{\{PLACEHOLDER:\s*([a-zA-Z0-9_]+)\s*\}\}")
LOGIN = re.compile(r"(?i)/(login|signin|sign-in|auth)(/|\?|$)")
SEVERITY = {
    "status_5xx": "critical", "robots_disallow_all": "critical", "sitemap_url_not_200": "critical",
    "home_unreachable": "critical",
    "missing_title": "high", "missing_description": "high", "h1_count": "high", "soft_404": "high",
    "missing_robots": "high", "missing_sitemap": "high", "noindex_in_sitemap": "high",
    "missing_viewport": "high", "status_4xx_linked": "high", "redirect_loop": "high",
    "jsonld_invalid": "high", "thin_html": "high",
    "missing_canonical": "medium", "canonical_mismatch": "medium", "missing_html_lang": "medium",
    "duplicate_title": "medium", "duplicate_description": "medium", "img_missing_alt": "medium",
    "orphan": "medium", "placeholder_left": "medium", "robots_no_sitemap_line": "medium",
    "status_4xx": "medium",
    "title_length": "low", "description_length": "low", "missing_og": "low", "deep_page": "low",
    "redirect_chain": "low", "thin_content": "low", "fetch_error": "high",
}
ORDER = ["critical", "high", "medium", "low"]


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
    except Exception as e:
        return {"status": None, "error": str(e)[:200], "headers": {}, "body": b""}
    if headers.get("Content-Encoding") == "gzip":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    return {"status": code, "headers": headers, "body": body}


def fetch(url, max_hops=8):
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
        self.meta, self.links, self.imgs, self.h1 = {}, [], [], []
        self.canonical, self.lang, self.jsonld, self.text = None, None, [], []
        self._skip, self._h1, self._ld = 0, None, None

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
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href")
        elif tag == "a" and "href" in a:
            self.links.append(a["href"])
        elif tag == "img":
            self.imgs.append({"src": a.get("src", "")[:200], "has_alt": "alt" in a})
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


def norm(u):
    p = parse.urlsplit(u)
    return parse.urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def to_base_host(u, base):
    pb, pu = parse.urlsplit(base), parse.urlsplit(u)
    if pu.netloc and pu.netloc != pb.netloc:
        return parse.urlunsplit((pb.scheme, pb.netloc, pu.path or "/", pu.query, ""))
    return u


def check_robots_and_sitemap(base, add):
    """Returns sitemap URLs (rewritten onto the crawl host)."""
    rb = fetch_once(parse.urljoin(base, "/robots.txt"))
    sitemaps = [parse.urljoin(base, "/sitemap.xml")]
    if rb["status"] != 200:
        add("missing_robots", parse.urljoin(base, "/robots.txt"), status=rb["status"])
    else:
        txt = rb["body"].decode("utf-8", "replace")
        agent_all, has_sitemap = False, False
        for raw in txt.splitlines():
            line = raw.split("#", 1)[0].strip()
            low = line.lower()
            if low.startswith("user-agent:"):
                agent_all = line.split(":", 1)[1].strip() == "*"
            elif low.startswith("disallow:") and agent_all and line.split(":", 1)[1].strip() == "/":
                add("robots_disallow_all", parse.urljoin(base, "/robots.txt"))
            elif low.startswith("sitemap:"):
                has_sitemap = True
                sitemaps.append(line.split(":", 1)[1].strip())
        if not has_sitemap:
            add("robots_no_sitemap_line", parse.urljoin(base, "/robots.txt"))
    urls, seen, found_any = [], set(), False
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    while sitemaps:
        sm = to_base_host(sitemaps.pop(), base)
        if sm in seen:
            continue
        seen.add(sm)
        r = fetch_once(sm)
        if r["status"] != 200:
            continue
        try:
            root = ET.fromstring(r["body"])
        except ET.ParseError:
            continue
        found_any = True
        for loc in root.iter(ns + "loc"):
            u = (loc.text or "").strip()
            if root.tag == ns + "sitemapindex":
                sitemaps.append(u)
            else:
                urls.append(u)
    if not found_any:
        add("missing_sitemap", parse.urljoin(base, "/sitemap.xml"))
    return [norm(to_base_host(u, base)) for u in urls]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--sitemap", action="store_true", help="check robots.txt + sitemap.xml and crawl sitemap URLs")
    ap.add_argument("--max-pages", type=int, default=150)
    ap.add_argument("--root", default=".", help="project root (JSON goes to <root>/mnm/seo-check.json)")
    a = ap.parse_args()
    base = a.base.rstrip("/") + "/"
    host = parse.urlsplit(base).netloc
    issues = []

    def add(t, url=None, **kw):
        issues.append({"type": t, "severity": SEVERITY.get(t, "medium"), "url": url, **kw})

    sm_urls = check_robots_and_sitemap(base, add) if a.sitemap else []
    sm_set = set(sm_urls)
    pages, depth, inlinks = {}, {norm(base): 0}, {}
    queue = deque([norm(base)])
    private = set()
    while queue and len(pages) < a.max_pages:
        url = queue.popleft()
        if url in pages or url in private:
            continue
        r = fetch(url)
        pg = {"url": url, "status": r["status"], "depth": depth.get(url)}
        if r.get("error"):
            add("home_unreachable" if url == norm(base) else "fetch_error", url, detail=r["error"])
            pages[url] = pg
            continue
        if r["chain"]:
            if LOGIN.search(parse.urlsplit(r["final_url"]).path + "?") and url not in sm_set:
                private.add(url)  # auth-protected app page: not for crawlers
                continue
            if r.get("loop"):
                add("redirect_loop", url)
            elif len(r["chain"]) > 1:
                add("redirect_chain", url, hops=len(r["chain"]))
        st = r["status"]
        if url in sm_set and st != 200:
            add("sitemap_url_not_200", url, status=st)
        if st and st >= 500:
            add("status_5xx", url, status=st)
        elif st and st >= 400 and url not in sm_set:
            add("status_4xx_linked" if inlinks.get(url) else "status_4xx", url, status=st,
                linked_from=inlinks.get(url, [])[:5])
        headers = r["headers"] or {}
        ctype = headers.get("Content-Type") or ""
        if st == 200 and "html" in ctype:
            html = r["body"].decode("utf-8", "replace")
            p = PageParser()
            try:
                p.feed(html)
            except Exception:
                pass
            robots = (p.meta.get("robots", "") + "," + (headers.get("X-Robots-Tag") or "")).lower()
            noindex = "noindex" in robots
            title = re.sub(r"\s+", " ", p.title).strip()
            desc = (p.meta.get("description") or "").strip()
            words = len(re.findall(r"\w+", " ".join(p.text), re.U))
            pg.update(title=title, description=desc, noindex=noindex, h1=p.h1, words=words)
            if noindex:
                if url in sm_set:
                    add("noindex_in_sitemap", url)
            else:
                if not title:
                    add("missing_title", url)
                elif not 15 <= len(title) <= 65:
                    add("title_length", url, length=len(title))
                if not desc:
                    add("missing_description", url)
                elif not 50 <= len(desc) <= 170:
                    add("description_length", url, length=len(desc))
                if len(p.h1) != 1:
                    add("h1_count", url, count=len(p.h1))
                if not p.canonical:
                    add("missing_canonical", url)
                elif norm(to_base_host(norm(parse.urljoin(url, p.canonical)), base)) != norm(r["final_url"]):
                    add("canonical_mismatch", url, canonical=p.canonical)
                if not p.meta.get("og:title"):
                    add("missing_og", url)
                if words < 30:
                    add("thin_html", url, words=words,
                        detail="almost no text in raw HTML: content is probably rendered client-side")
                elif words < 80:
                    add("thin_content", url, words=words, detail="short page; fine for utility pages")
            if not p.meta.get("viewport"):
                add("missing_viewport", url)
            if not p.lang:
                add("missing_html_lang", url)
            missing_alt = [i["src"] for i in p.imgs if not i["has_alt"]]
            if missing_alt:
                add("img_missing_alt", url, count=len(missing_alt), sample=missing_alt[:3])
            ph = sorted(set(PLACEHOLDER.findall(html)))
            if ph:
                add("placeholder_left", url, names=ph)
            bad_ld = 0
            for b in p.jsonld:
                try:
                    json.loads(b)
                except ValueError:
                    bad_ld += 1
            if bad_ld:
                add("jsonld_invalid", url, blocks=bad_ld)
            for href in p.links:
                href = href.strip()
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "sms:")):
                    continue
                absu = norm(parse.urljoin(r["final_url"], href))
                if parse.urlsplit(absu).netloc != host or SKIP_EXT.search(parse.urlsplit(absu).path):
                    continue
                inlinks.setdefault(absu, [])
                if url not in inlinks[absu]:
                    inlinks[absu].append(url)
                depth.setdefault(absu, (depth.get(url) or 0) + 1)
                if absu not in pages and absu not in queue:
                    queue.append(absu)
        pages[url] = pg
        if not queue and sm_urls:
            queue.extend(u for u in sm_urls if u not in pages)
            sm_urls = []

    indexable = [p for p in pages.values() if p.get("status") == 200 and "title" in p and not p.get("noindex")]
    for field, t in (("title", "duplicate_title"), ("description", "duplicate_description")):
        groups = {}
        for p in indexable:
            if p.get(field):
                groups.setdefault(p[field], []).append(p["url"])
        for v, us in groups.items():
            if len(us) > 1:
                add(t, None, value=v[:100], urls=us[:10])
    home = norm(base)
    for u, p in pages.items():
        if u != home and p.get("status") == 200 and not inlinks.get(u) and not p.get("noindex"):
            add("orphan", u)
        if (depth.get(u) or 0) > 3 and p.get("status") == 200:
            add("deep_page", u, depth=depth.get(u))

    probe = parse.urljoin(base, f"/mnm-404-probe-{uuid.uuid4().hex[:8]}")
    if fetch(probe)["status"] == 200:
        add("soft_404", probe, detail="unknown URL returns 200; must return 404")

    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ORDER}
    out = {"base": base, "crawled": len(pages), "private_skipped": len(private), "counts": counts,
           "issues": sorted(issues, key=lambda i: ORDER.index(i["severity"])), "pages": list(pages.values())}
    path = os.path.join(os.path.abspath(a.root), "mnm", "seo-check.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"seo_check: {len(pages)} pages crawled ({len(private)} private skipped) · "
          f"{counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low"
          f" → mnm/seo-check.json")
    for i in out["issues"][:25]:
        extra = {k: v for k, v in i.items() if k not in ("type", "severity", "url")}
        print(f"  [{i['severity']}] {i['type']} {i['url'] or ''} {json.dumps(extra, ensure_ascii=False)[:140] if extra else ''}")
    return 1 if counts["critical"] or counts["high"] else 0


if __name__ == "__main__":
    sys.exit(main())
