"""Shared helpers for the develop-frontend scripts.

find_docs.py and ensure_gitignore.py use the standard library only. shoot.py, browse.py and
ui_audit.py also need Playwright (`pip install playwright && python -m playwright install chromium`).
"""
import json
import os
import re
import sys
import time

DESIGN = "DESIGN"
WORK = os.path.join(DESIGN, ".work")
DEFAULT_WIDTHS = [360, 390, 768, 1280, 1440]
DEFAULT_HEIGHT = 900
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".svelte-kit", ".next", ".nuxt", ".turbo", ".cache", "dist", "build", "out",
    "coverage", "test-results", "playwright-report", ".output", "target", "vendor", ".idea",
    ".vscode", "tmp", "DESIGN", "mnm", ".claude", "bower_components", ".gradle", "Pods",
}
PLAYWRIGHT_HINT = ("Playwright is not installed. Run:\n"
                   "  python -m pip install playwright\n"
                   "  python -m playwright install chromium")


def design_path(root, *parts):
    return os.path.join(root, DESIGN, *parts)


def work_path(root, *parts):
    return os.path.join(root, WORK, *parts)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for _ in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a reader holds the file for a moment
            time.sleep(0.1)
    os.replace(tmp, path)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def utf8_stdout():
    """Windows consoles default to cp1252; route output through UTF-8 so Turkish etc. survives."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def parse_widths(text):
    if not text:
        return list(DEFAULT_WIDTHS)
    return [int(w) for w in re.split(r"[,\s]+", text.strip()) if w]


MSYS_MANGLED = re.compile(r"^[A-Za-z]:[/\\](?:Program Files[/\\])?Git[/\\]?(.*)$", re.I)


def unmangle(route):
    """Git Bash rewrites a leading "/menu" argument to "C:/Program Files/Git/menu"; undo that."""
    m = MSYS_MANGLED.match(route)
    return "/" + m.group(1).replace("\\", "/") if m else route


def parse_routes(routes, routes_file=None):
    """--routes "/,/menu,/cart" and/or --routes-file (one route per line, # comments)."""
    out = []
    if routes:
        out += [r.strip() for r in routes.split(",") if r.strip()]
    if routes_file:
        with open(routes_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    out.append(line)
    seen, uniq = set(), []
    for r in [unmangle(r) for r in out] or ["/"]:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def route_expect(route):
    """"/missing [404]" -> ("/missing", 404): a route that is supposed to return that status."""
    m = re.match(r"^(.*?)\s+\[(\d{3})\]$", route.strip())
    return (m.group(1), int(m.group(2))) if m else (route.strip(), None)


def join_url(base, route):
    if re.match(r"^https?://", route):
        return route
    return base.rstrip("/") + "/" + route.lstrip("/")


def slug(route):
    s = re.sub(r"^https?://[^/]+", "", route).strip("/") or "home"
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s[:80] or "home"


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print(PLAYWRIGHT_HINT, file=sys.stderr)
        sys.exit(3)
    from playwright.sync_api import sync_playwright
    return sync_playwright


def launch(pw, headed=False):
    try:
        return pw.chromium.launch(headless=not headed)
    except Exception as e:  # browser binary missing
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            print(PLAYWRIGHT_HINT, file=sys.stderr)
            sys.exit(3)
        raise


def new_page(browser, width, height=DEFAULT_HEIGHT, color_scheme="light", locale=None,
             reduced_motion="no-preference"):
    mobile = width < 768
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        is_mobile=mobile,
        has_touch=mobile,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale=locale,
    )
    page = ctx.new_page()
    log = {"console_errors": [], "page_errors": [], "failed_requests": []}
    page.on("console", lambda m: m.type == "error" and log["console_errors"].append(m.text[:300]))
    page.on("pageerror", lambda e: log["page_errors"].append(str(e)[:300]))
    page.on("requestfailed", lambda r: log["failed_requests"].append(
        f"{r.method} {r.url[:200]} ({r.failure})"))
    page.on("response", lambda r: r.status >= 400 and r.request.resource_type in
            ("fetch", "xhr", "document", "script", "stylesheet", "image", "font") and
            log["failed_requests"].append(f"{r.status} {r.request.method} {r.url[:200]}"))
    return ctx, page, log


def settle(page, wait_ms=600):
    """Wait for network idle (bounded), then a little longer for entrance animations."""
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(wait_ms)
