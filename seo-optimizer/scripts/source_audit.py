"""Static SEO inventory of a website project's source (no build, no server needed).

Detects the stack and routes, existing SEO assets (metadata, robots, sitemap, JSON-LD), and
crawlability risks in the source: page/layout-level 'use client', JS-only navigation, images
without alt, H1 counts, client-side fetching of content, leftover placeholders. Also lists the
backend paths the agent must not touch.

Usage:
  python source_audit.py --root .                 # whole project
  python source_audit.py --root . --files a.tsx b.html   # only these files (after changes)
Prints JSON (use --out to also write it to a file).
"""
import argparse
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".next", ".nuxt", ".output", ".svelte-kit", ".astro", "dist", "build",
             "out", ".git", ".vercel", ".netlify", "coverage", ".turbo", ".cache", "seo", "__pycache__",
             ".venv", "venv"}
CODE_EXT = {".tsx", ".jsx", ".ts", ".js", ".mjs", ".vue", ".svelte", ".astro", ".html", ".htm", ".mdx", ".md"}
PAGE_EXT = (".tsx", ".jsx", ".ts", ".js", ".mdx")

BACKEND_GLOBS = [
    ("app/api", "Next.js route handlers"), ("src/app/api", "Next.js route handlers"),
    ("pages/api", "Next.js API routes"), ("src/pages/api", "Next.js API routes"),
    ("server", "server code"), ("src/server", "server code"), ("api", "serverless functions"),
    ("prisma", "ORM schema/migrations"), ("drizzle", "ORM"), ("db", "database"), ("src/db", "database"),
    ("lib/db", "database"), ("models", "data models"), ("supabase", "backend config"),
    ("functions", "serverless functions"), ("netlify/functions", "serverless functions"),
    ("src/routes/api", "SvelteKit endpoints"), ("server/api", "Nuxt server routes"),
]
ASK_FIRST = ["middleware.ts", "middleware.js", "src/middleware.ts", "next.config.js", "next.config.mjs",
             "next.config.ts", "vercel.json", "netlify.toml", "nginx.conf", "_redirects", "_headers",
             "astro.config.mjs", "nuxt.config.ts", "svelte.config.js", "vite.config.ts", "vite.config.js"]

RE_USE_CLIENT = re.compile(r"""^\s*(?:/\*.*?\*/\s*|//[^\n]*\n\s*)*['"]use client['"]""", re.S)
RE_USE_SERVER = re.compile(r"""['"]use server['"]""")
RE_IMG_NO_ALT = re.compile(r"<(img|Image|NuxtImg|Picture)\b(?![^>]*\balt\s*=)[^>]*>", re.S)
RE_H1 = re.compile(r"<h1\b", re.I)
RE_JS_NAV = re.compile(r"onClick\s*=\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*?(router\.(?:push|replace)\(|navigate\(|"
                       r"window\.location(?:\.href)?\s*=|location\.assign\()", re.S)
RE_CLICK_NAV_VUE = re.compile(r"@click\s*=\s*\"[^\"]*(\$router\.push|router\.push|navigateTo)\(")
RE_PLACEHOLDER = re.compile(r"\{\{PLACEHOLDER:\s*([a-zA-Z0-9_]+)\s*\}\}")
RE_JSONLD = re.compile(r"application/ld\+json")
RE_META_EXPORT = re.compile(r"export\s+(const\s+metadata\b|(async\s+)?function\s+generateMetadata\b)")
RE_FETCH_IN_EFFECT = re.compile(r"useEffect\s*\(\s*(?:async\s*)?\(\)\s*=>\s*\{[^}]*\bfetch\(|useEffect[\s\S]{0,400}?\bfetch\(")
RE_HTML_LANG = re.compile(r"<html[^>]*\blang\s*=", re.I)
RE_BACKEND_IMPORT = re.compile(r"""from\s+['"](@prisma/client|drizzle-orm[^'"]*|mongoose|pg|mysql2|redis|ioredis|stripe|"""
                               r"""@supabase/supabase-js|firebase-admin[^'"]*|bcrypt[^'"]*|jsonwebtoken|next-auth[^'"]*)['"]""")
RE_SPA_ROUTE = re.compile(r"""<Route\b[^>]*\bpath\s*=\s*["']([^"']+)["']|\bpath\s*:\s*["'](/[^"']*)["']""")


def rel(root, p):
    return os.path.relpath(p, root).replace("\\", "/")


def read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def walk(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for f in files:
            yield os.path.join(d, f)


def load_pkg(root):
    p = os.path.join(root, "package.json")
    if not os.path.exists(p):
        return None
    try:
        return json.loads(read(p))
    except json.JSONDecodeError:
        return {}


def detect_stack(root, pkg, files):
    deps = {}
    if pkg:
        deps.update(pkg.get("dependencies") or {})
        deps.update(pkg.get("devDependencies") or {})
    has = lambda *ds: any(d in deps for d in ds)
    exists = lambda *ps: any(os.path.isdir(os.path.join(root, p)) for p in ps)
    if has("next"):
        if exists("app", "src/app"):
            return "nextjs-app" + ("+pages" if exists("pages", "src/pages") else "")
        return "nextjs-pages"
    if has("astro"):
        return "astro"
    if has("nuxt", "nuxt3"):
        return "nuxt"
    if has("@sveltejs/kit"):
        return "sveltekit"
    if has("@remix-run/react", "@react-router/dev"):
        return "remix"
    if has("gatsby"):
        return "gatsby"
    if has("react-scripts"):
        return "cra-spa"
    if has("vite") and has("react", "react-dom"):
        return "vite-react-spa"
    if has("vite") and has("vue"):
        return "vite-vue-spa"
    if has("react"):
        return "react-unknown"
    html = [f for f in files if f.lower().endswith((".html", ".htm"))]
    if html:
        return "static-html"
    meaningful = [f for f in files if not os.path.basename(f).startswith(".")
                  and os.path.basename(f).lower() not in {"readme.md", "license", "license.md"}]
    return "blank" if not meaningful else "unknown"


def route_from_file(stack, r):
    """Map a source file (relative path) to a URL route, or None if it's not a page."""
    p = r
    if stack.startswith("nextjs-app"):
        m = re.match(r"^(?:src/)?app/(.*?)(?:/)?page\.(tsx|jsx|ts|js|mdx)$", p)
        if m:
            segs = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")"))
                    and not s.startswith("@")]
            return "/" + "/".join(segs)
    if stack.startswith("nextjs") or stack == "gatsby":
        m = re.match(r"^(?:src/)?pages/(.*)\.(tsx|jsx|ts|js|mdx)$", p)
        if m and not m.group(1).startswith(("api/", "_")):
            return "/" + re.sub(r"(^|/)index$", "", m.group(1))
    if stack == "astro":
        m = re.match(r"^src/pages/(.*)\.(astro|md|mdx|html)$", p)
        if m:
            return "/" + re.sub(r"(^|/)index$", "", m.group(1))
    if stack == "nuxt":
        m = re.match(r"^(?:app/)?pages/(.*)\.vue$", p)
        if m:
            return "/" + re.sub(r"(^|/)index$", "", m.group(1))
    if stack == "sveltekit":
        m = re.match(r"^src/routes/(.*?)/?\+page\.svelte$", p)
        if m:
            segs = [s for s in m.group(1).split("/") if s and not s.startswith("(")]
            return "/" + "/".join(segs)
    if stack == "static-html" and p.lower().endswith((".html", ".htm")):
        if any(x in p for x in ("node_modules/",)):
            return None
        route = "/" + p
        route = re.sub(r"(^|/)index\.html?$", r"\1", route)
        return route
    return None


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def audit_file(root, path, stack, is_page, is_layout):
    t = read(path)
    r = rel(root, path)
    f = {"file": r, "issues": []}
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tsx", ".jsx", ".ts", ".js") and RE_USE_CLIENT.match(t):
        f["use_client"] = True
        if is_page or is_layout:
            f["issues"].append({"type": "page_level_use_client",
                                "detail": "Whole page/layout is a client component; move 'use client' to interactive leaves."})
    if RE_USE_SERVER.search(t):
        f["use_server"] = True
    for m in RE_JS_NAV.finditer(t):
        f["issues"].append({"type": "js_navigation", "line": line_of(t, m.start()),
                            "detail": "Navigation via onClick handler; crawlers need <a href>/<Link href>."})
    for m in RE_CLICK_NAV_VUE.finditer(t):
        f["issues"].append({"type": "js_navigation", "line": line_of(t, m.start()),
                            "detail": "Navigation via @click; use <NuxtLink to>/<router-link to>/<a href>."})
    for m in RE_IMG_NO_ALT.finditer(t):
        f["issues"].append({"type": "img_missing_alt", "line": line_of(t, m.start()),
                            "detail": m.group(0)[:120].replace("\n", " ")})
    h1 = len(RE_H1.findall(t))
    f["h1_count"] = h1
    if is_page and h1 > 1:
        f["issues"].append({"type": "multiple_h1", "detail": f"{h1} <h1> tags in this file"})
    if ext in (".tsx", ".jsx", ".ts", ".js") and RE_FETCH_IN_EFFECT.search(t):
        f["issues"].append({"type": "client_fetch",
                            "detail": "fetch() inside useEffect: if this loads page content, it is invisible in the initial HTML."})
    ph = sorted(set(RE_PLACEHOLDER.findall(t)))
    if ph:
        f["placeholders"] = ph
    if RE_JSONLD.search(t):
        f["jsonld"] = True
    if is_page and stack.startswith("nextjs-app"):
        f["has_metadata_export"] = bool(RE_META_EXPORT.search(t))
        if not f["has_metadata_export"] and r.split("/")[-1].startswith("page"):
            f["issues"].append({"type": "no_page_metadata",
                                "detail": "No metadata/generateMetadata export: title/description fall back to the layout (likely duplicate)."})
    if is_page and stack == "nextjs-pages" and "next/head" not in t:
        f["issues"].append({"type": "no_page_metadata", "detail": "No next/head usage in page."})
    if ext in (".html", ".htm"):
        checks = {
            "missing_title": r"<title>\s*[^<\s]",
            "missing_description": r"<meta[^>]+name=[\"']description[\"']",
            "missing_canonical": r"<link[^>]+rel=[\"']canonical[\"']",
            "missing_viewport": r"<meta[^>]+name=[\"']viewport[\"']",
        }
        for k, rx in checks.items():
            if not re.search(rx, t, re.I):
                f["issues"].append({"type": k})
        if not RE_HTML_LANG.search(t):
            f["issues"].append({"type": "missing_html_lang"})
        tm = re.search(r"<title>(.*?)</title>", t, re.I | re.S)
        if tm:
            f["title"] = re.sub(r"\s+", " ", tm.group(1)).strip()
    if is_layout and stack.startswith("nextjs-app") and "<html" in t and not RE_HTML_LANG.search(t):
        f["issues"].append({"type": "missing_html_lang"})
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    all_files = list(walk(root))
    pkg = load_pkg(root)
    stack = detect_stack(root, pkg, all_files)

    backend = []
    for g, why in BACKEND_GLOBS:
        if os.path.isdir(os.path.join(root, g)):
            backend.append({"path": g + "/**", "why": why})
    for e in sorted(x for x in os.listdir(root) if x.startswith(".env")):
        backend.append({"path": e, "why": "environment secrets"})
    ask_first = [p for p in ASK_FIRST if os.path.exists(os.path.join(root, p))]

    def under_backend_dir(r):
        return any(r.startswith(b["path"][:-3] + "/") for b in backend if b["path"].endswith("/**"))

    # Individual files that are backend because of what they import (lib/db.ts, auth.ts, ...)
    for f in all_files:
        r = rel(root, f)
        if os.path.splitext(f)[1].lower() in (".ts", ".js", ".mjs") and not under_backend_dir(r) \
                and RE_BACKEND_IMPORT.search(read(f)):
            backend.append({"path": r, "why": "imports a database/auth/payment server library"})

    def is_backend(r):
        return under_backend_dir(r) or any(r == b["path"] for b in backend) or os.path.basename(r).startswith(".env")

    targets = [os.path.join(root, f) for f in a.files] if a.files else \
        [f for f in all_files if os.path.splitext(f)[1].lower() in CODE_EXT]

    routes, files_out, use_server_files = [], [], []
    seo_assets = {"robots": [], "sitemap": [], "not_found": [], "manifest": []}
    for f in all_files:
        r = rel(root, f)
        b = os.path.basename(r).lower()
        if b in ("robots.txt", "robots.ts", "robots.js"):
            seo_assets["robots"].append(r)
        if b.startswith("sitemap") and b.split(".")[-1] in ("xml", "ts", "js", "mjs"):
            seo_assets["sitemap"].append(r)
        if b.startswith(("not-found.", "404.", "+error.", "error.vue")):
            seo_assets["not_found"].append(r)

    for f in targets:
        if not os.path.exists(f):
            continue
        r = rel(root, f)
        if is_backend(r) or r.startswith("seo/"):
            continue
        route = route_from_file(stack, r)
        base = os.path.basename(r)
        is_layout = base.startswith(("layout.", "_app.", "_document.", "+layout.", "app.vue", "Layout.", "BaseHead"))
        res = audit_file(root, f, stack, route is not None, is_layout)
        if res.get("use_server"):
            use_server_files.append(r)
        if route is not None:
            res["route"] = route
            routes.append(route)
        if stack.endswith("-spa") or stack == "react-unknown":
            for m in RE_SPA_ROUTE.finditer(read(f)):
                routes.append(m.group(1) or m.group(2))
        if res["issues"] or route is not None or res.get("placeholders") or res.get("jsonld"):
            files_out.append(res)

    project_issues = []
    if stack.endswith("-spa") or stack == "react-unknown":
        project_issues.append({"type": "client_only_rendering",
                               "detail": "Client-side SPA: the first HTML is an empty root div and every route shares one "
                                         "<title>. Propose prerendering/SSG (references/technical-seo.md section 7)."})
    counts = {i["type"]: 1 for i in project_issues}
    for f in files_out:
        for i in f["issues"]:
            counts[i["type"]] = counts.get(i["type"], 0) + 1
    placeholders = sorted({p for f in files_out for p in f.get("placeholders", [])})

    titles = {}
    for f in files_out:
        if f.get("title"):
            titles.setdefault(f["title"], []).append(f["file"])
    dup_titles = {t: fs for t, fs in titles.items() if len(fs) > 1}

    out = {
        "root": root,
        "stack": stack,
        "package_scripts": (pkg or {}).get("scripts") if pkg else None,
        "node_modules_installed": os.path.isdir(os.path.join(root, "node_modules")),
        "routes": sorted(set(routes)),
        "seo_assets": seo_assets,
        "jsonld_files": [f["file"] for f in files_out if f.get("jsonld")],
        "backend_readonly": backend,
        "server_action_files": use_server_files,
        "ask_before_touching": ask_first,
        "project_issues": project_issues,
        "issue_counts": counts,
        "duplicate_titles": dup_titles,
        "placeholders": placeholders,
        "files": files_out,
    }
    s = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(s)
    print(s)


if __name__ == "__main__":
    sys.exit(main())
