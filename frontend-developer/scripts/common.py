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


# Records, for every element with its own text that is inside the viewport right now, whether it is
# visible (effective opacity >= 0.1). Called once per scroll step. Things hidden on purpose (closed
# menus, tooltips, visibility:hidden, opacity 0 + pointer-events:none overlays) are ignored.
TRACK_JS = r"""
() => {
  const W = window.__revealSeen || (window.__revealSeen = {vis: new WeakSet(), invis: new Set()});
  const vh = innerHeight, vw = innerWidth;
  let n = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (++n > 4000) break;
    if (!el.childNodes.length) continue;
    let own = false;
    for (const c of el.childNodes) if (c.nodeType === 3 && c.textContent.trim().length > 1) { own = true; break; }
    if (!own) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
    // closed menus, tooltips and dialogs are hidden on purpose
    if (el.closest('[aria-hidden="true"],[data-state="closed"],[role="tooltip"],[inert],[hidden]')) continue;
    let op = 1, skip = false;
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === 'none' || s.visibility === 'hidden') { skip = true; break; }
      const o = parseFloat(s.opacity);
      if (o < 0.1 && s.pointerEvents === 'none') { skip = true; break; } // hidden overlay, not an entrance
      op *= o;
    }
    if (skip) continue;
    if (op >= 0.1) { W.vis.add(el); W.invis.delete(el); }
    else if (!W.vis.has(el)) W.invis.add(el);
  }
}
"""

STUCK_JS = r"""
() => {
  const W = window.__revealSeen; if (!W) return [];
  const out = [];
  const describe = el => {
    const parts = [];
    for (let e = el, i = 0; e && e.nodeType === 1 && i < 4 && e !== document.body; e = e.parentElement, i++) {
      let p = e.tagName.toLowerCase();
      if (e.id && !/\d{3,}/.test(e.id)) { parts.unshift(p + '#' + e.id); break; }
      const cls = [...e.classList].filter(c => c.length < 30 && !/[:\[\]\/]/.test(c)).slice(0, 2);
      if (cls.length) p += '.' + cls.join('.');
      parts.unshift(p);
    }
    return parts.join(' > ');
  };
  for (const el of W.invis) {
    if (!el.isConnected || W.vis.has(el)) continue;
    const r = el.getBoundingClientRect();
    out.push({selector: describe(el), text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 50),
              rect: {x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height)}});
    if (out.length >= 12) break;
  }
  return out;
}
"""


def reveal_all(page, step_wait=350, max_steps=40, track=False):
    """Scroll down one viewport at a time so scroll-triggered entrance animations (IntersectionObserver,
    GSAP ScrollTrigger, React Bits AnimatedContent/FadeContent/SplitText…) fire, then return to the top.

    A full-page screenshot never scrolls, so without this every section below the first screen stays at
    opacity 0. With track=True it returns the text elements that were *in view and still invisible* at
    every step: content whose animation never fires (stuck-invisible). Scroll-linked (scrub) effects are
    judged while they are in view, so they don't count as stuck.
    """
    stuck = []
    try:
        vh = page.evaluate("innerHeight")
        step = max(200, int(vh * 0.7))
        y = 0
        for _ in range(max_steps):
            if track:
                page.evaluate(TRACK_JS)
            height = page.evaluate("document.documentElement.scrollHeight")
            if y + vh >= height:
                break
            y += step
            page.mouse.wheel(0, step)  # real wheel events: smooth-scroll libraries (Lenis) follow them
            page.wait_for_timeout(step_wait)
            if page.evaluate("scrollY") + 5 < min(y, height - vh):  # wheel ignored: scroll directly
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(step_wait)
        if track:
            page.wait_for_timeout(step_wait)
            page.evaluate(TRACK_JS)
            stuck = page.evaluate(STUCK_JS)
        page.evaluate("window.scrollTo(0, 0)")
        page.mouse.wheel(0, -100000)
        page.wait_for_timeout(500)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
    except Exception:
        pass
    return stuck
