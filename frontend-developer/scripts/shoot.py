"""Screenshot every route at every width (Playwright, Chromium).

This is how the user persona *looks at* the site. It never reads source code.

Usage:
  python shoot.py --url http://localhost:5173 --routes "/,/menu,/cart" --out DESIGN/.work/reviews/round-1/shots
                  [--routes-file routes.txt] [--widths 360,390,768,1280,1440] [--height 900]
                  [--viewport-only] [--max-height 6000] [--dark] [--reduced-motion] [--wait 600]

Writes <out>/<route-slug>@<width>.png (+ -dark suffix with --dark) and <out>/index.json with the
HTTP status, title, console errors, page errors and failed requests for each shot. Prints a short
summary. Full-page shots taller than --max-height are clipped (tall images become unreadable).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (join_url, launch, route_expect, new_page, parse_routes, parse_widths, require_playwright,  # noqa: E402
                    save_json, settle, slug, utf8_stdout)


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--routes", default="")
    ap.add_argument("--routes-file")
    ap.add_argument("--widths", default="")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--out", required=True)
    ap.add_argument("--viewport-only", action="store_true")
    ap.add_argument("--max-height", type=int, default=6000)
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--reduced-motion", action="store_true")
    ap.add_argument("--wait", type=int, default=600, help="ms to wait after load for animations")
    ap.add_argument("--locale")
    a = ap.parse_args()

    routes = parse_routes(a.routes, a.routes_file)
    widths = parse_widths(a.widths)
    os.makedirs(a.out, exist_ok=True)
    sync_playwright = require_playwright()
    shots = []
    with sync_playwright() as pw:
        browser = launch(pw)
        for width in widths:
            for route_line in routes:
                route, expected = route_expect(route_line)
                ctx, page, log = new_page(browser, width, a.height,
                                          color_scheme="dark" if a.dark else "light",
                                          locale=a.locale,
                                          reduced_motion="reduce" if a.reduced_motion else "no-preference")
                url = join_url(a.url, route)
                status, title, err = None, "", None
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    status = resp.status if resp else None
                    settle(page, a.wait)
                    title = page.title()
                except Exception as e:
                    err = str(e).splitlines()[0][:300]
                name = f"{slug(route)}@{width}{'-dark' if a.dark else ''}.png"
                path = os.path.join(a.out, name)
                page_height = None
                try:
                    page_height = page.evaluate("document.documentElement.scrollHeight")
                    if a.viewport_only:
                        page.screenshot(path=path)
                    elif page_height and page_height > a.max_height:
                        page.screenshot(path=path, full_page=True,
                                        clip={"x": 0, "y": 0, "width": width, "height": a.max_height})
                    else:
                        page.screenshot(path=path, full_page=True)
                except Exception as e:
                    err = err or str(e).splitlines()[0][:300]
                shots.append({"route": route, "width": width, "file": name, "status": status,
                              "expected": expected,
                              "title": title, "page_height": page_height,
                              "clipped": bool(page_height and not a.viewport_only and page_height > a.max_height),
                              "error": err, **log})
                ctx.close()
        browser.close()

    save_json(os.path.join(a.out, "index.json"), {"url": a.url, "shots": shots})
    bad = [s for s in shots if s["error"] or ((s["status"] or 0) >= 400 and s["status"] != s["expected"])]
    noisy = [s for s in shots if s["console_errors"] or s["page_errors"]]
    print(f"{len(shots)} screenshots -> {a.out}")
    for s in bad:
        print(f"  FAIL {s['route']} @{s['width']}: status={s['status']} {s['error'] or ''}")
    for s in noisy:
        errs = (s["page_errors"] + s["console_errors"])[:2]
        print(f"  JS-ERRORS {s['route']} @{s['width']}: {' | '.join(errs)}")
    for s in shots:
        if s["clipped"]:
            print(f"  CLIPPED {s['file']} (page is {s['page_height']}px; use browse.py scroll to see the rest)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
