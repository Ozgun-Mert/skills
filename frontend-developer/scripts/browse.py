"""Use the site like a person: replay a list of steps and screenshot after each one (Playwright).

The user persona completes its tasks with this script. Every call starts a fresh browser and
replays ALL steps from the top, so runs are deterministic. To go further, append steps to the same
file and run again. After the last step (or the first failing one) it prints what is on screen:
the visible text and the clickable elements, with their names and positions. That is all the
persona needs to decide its next step. It never reads the source code.

Usage:
  python browse.py --url http://localhost:5173 --steps steps.json --out DESIGN/.work/reviews/round-1/task-2
                   [--width 390] [--height 844] [--dark] [--locale tr-TR]

steps.json is a JSON list. Each item is one action ("note" is optional, for the report):
  {"goto": "/menu"}
  {"click": "Add to cart"}                         text → button, link, label, placeholder, then any text
  {"click": {"role": "button", "name": "Add", "nth": 1}}
  {"click": {"text": "Lahmacun"}} | {"click": {"label": "Email"}} | {"click": {"selector": "css"}}
  {"click": {"at": [195, 600]}}                    coordinates on the current viewport screenshot
  {"fill": {"label": "Email", "text": "a@b.co"}}    any target key + "text"
  {"type": "hello"}  {"press": "Enter"}
  {"select": {"label": "Size", "option": "Large"}}
  {"check": "I accept"}  {"uncheck": "Newsletter"}  {"hover": "Menu"}
  {"scroll": 600} | {"scroll": "bottom"} | {"scroll": "top"} | {"scroll": {"text": "Reviews"}}
  {"wait": 800}  {"back": true}  {"screenshot": "after-payment"} (full page)
  {"expect": "Order received"}                     passes when that text is visible
Writes <out>/step-NN.png (viewport) and <out>/run.json. Exit code 0 = all steps passed.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import join_url, launch, new_page, require_playwright, save_json, settle, utf8_stdout  # noqa: E402

TARGET_KEYS = {"role", "name", "text", "label", "placeholder", "selector", "testid", "at", "nth",
               "exact"}

SNAPSHOT_JS = r"""
() => {
  const vw = innerWidth, vh = innerHeight;
  const vis = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05;
  };
  const sel = 'a[href],button,input,select,textarea,summary,label,[role=button],[role=link],[role=tab],' +
              '[role=menuitem],[role=checkbox],[role=radio],[role=switch],[onclick],[tabindex="0"]';
  const items = [];
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    let name = el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) ||
               el.innerText || el.value || el.getAttribute('placeholder') || el.title ||
               (el.querySelector('img') && el.querySelector('img').alt) || '';
    name = name.replace(/\s+/g, ' ').trim().slice(0, 60);
    items.push({tag: el.tagName.toLowerCase() + (el.type ? ':' + el.type : ''),
                role: el.getAttribute('role') || '', name,
                x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                w: Math.round(r.width), h: Math.round(r.height),
                cursor: getComputedStyle(el).cursor, disabled: !!el.disabled});
    if (items.length >= 70) break;
  }
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n, total = 0;
  while ((n = walker.nextNode()) && total < 2500) {
    const t = n.textContent.replace(/\s+/g, ' ').trim();
    if (!t || !n.parentElement || !vis(n.parentElement)) continue;
    texts.push(t); total += t.length + 1;
  }
  return {url: location.href, title: document.title, scrollY: Math.round(scrollY),
          pageHeight: document.documentElement.scrollHeight, viewport: [vw, vh],
          visibleText: texts.join(' | ').slice(0, 2500), clickables: items};
}
"""


def first_visible(loc, nth=None):
    count = loc.count()
    if nth is not None:
        return loc.nth(nth) if count > nth else None
    for i in range(min(count, 15)):
        cand = loc.nth(i)
        try:
            if cand.is_visible():
                return cand
        except Exception:
            continue
    return None


def locate(page, spec):
    """Return a Locator (or ("at", x, y)) for a target spec, or raise LookupError."""
    if isinstance(spec, str):
        spec = {"text": spec, "_loose": True}
    if "at" in spec:
        x, y = spec["at"]
        return ("at", x, y)
    nth = spec.get("nth")
    exact = spec.get("exact", False)
    tries = []
    if "selector" in spec:
        tries.append(page.locator(spec["selector"]))
    if "testid" in spec:
        tries.append(page.get_by_test_id(spec["testid"]))
    if "role" in spec:
        tries.append(page.get_by_role(spec["role"], name=spec.get("name"), exact=exact)
                     if spec.get("name") else page.get_by_role(spec["role"]))
    if "label" in spec:
        tries.append(page.get_by_label(spec["label"], exact=exact))
    if "placeholder" in spec:
        tries.append(page.get_by_placeholder(spec["placeholder"], exact=exact))
    if "text" in spec:
        t = spec["text"]
        if spec.get("_loose"):
            for role in ("button", "link", "tab", "menuitem", "checkbox", "radio", "option"):
                tries.append(page.get_by_role(role, name=t, exact=exact))
            tries.append(page.get_by_label(t, exact=exact))
            tries.append(page.get_by_placeholder(t, exact=exact))
        tries.append(page.get_by_text(t, exact=exact))
    for loc in tries:
        found = first_visible(loc, nth)
        if found is not None:
            return found
    raise LookupError(f"nothing visible matches {json.dumps({k: v for k, v in spec.items() if k != '_loose'}, ensure_ascii=False)}")


def target_of(value):
    if isinstance(value, dict):
        t = {k: v for k, v in value.items() if k in TARGET_KEYS}
        return t if t else value
    return value


def do_click(page, value):
    loc = locate(page, target_of(value))
    if isinstance(loc, tuple):
        page.mouse.click(loc[1], loc[2])
    else:
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=5000)


def run_step(page, base, step):
    kind = next((k for k in step if k != "note"), None)
    v = step.get(kind)
    if kind == "goto":
        page.goto(join_url(base, v), wait_until="domcontentloaded", timeout=30000)
    elif kind == "click":
        do_click(page, v)
    elif kind == "fill":
        loc = locate(page, target_of(v))
        loc.fill(str(v["text"]), timeout=5000)
    elif kind == "type":
        page.keyboard.type(str(v), delay=20)
    elif kind == "press":
        page.keyboard.press(v)
    elif kind == "select":
        loc = locate(page, target_of(v))
        loc.select_option(label=v["option"], timeout=5000)
    elif kind in ("check", "uncheck"):
        loc = locate(page, target_of(v))
        (loc.check if kind == "check" else loc.uncheck)(timeout=5000)
    elif kind == "hover":
        loc = locate(page, target_of(v))
        if isinstance(loc, tuple):
            page.mouse.move(loc[1], loc[2])
        else:
            loc.hover(timeout=5000)
    elif kind == "scroll":
        if v == "bottom":
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        elif v == "top":
            page.evaluate("window.scrollTo(0, 0)")
        elif isinstance(v, (int, float)):
            page.mouse.wheel(0, v)
        else:
            locate(page, target_of(v)).scroll_into_view_if_needed(timeout=5000)
    elif kind == "wait":
        page.wait_for_timeout(int(v))
    elif kind == "back":
        page.go_back(wait_until="domcontentloaded")
    elif kind == "screenshot":
        return {"full_page": True, "name": str(v)}
    elif kind == "expect":
        loc = first_visible(page.get_by_text(str(v), exact=False))
        if loc is None:
            raise AssertionError(f"expected text not visible: {v!r}")
    else:
        raise ValueError(f"unknown step {step!r}")
    return None


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=844)
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--locale")
    a = ap.parse_args()

    with open(a.steps, "r", encoding="utf-8") as f:
        steps = json.load(f)
    if not steps or "goto" not in steps[0]:
        steps = [{"goto": "/"}] + steps
    os.makedirs(a.out, exist_ok=True)
    for old in os.listdir(a.out):
        if old.startswith("step-") and old.endswith(".png"):
            os.remove(os.path.join(a.out, old))

    sync_playwright = require_playwright()
    results, failed, snapshot = [], None, None
    with sync_playwright() as pw:
        browser = launch(pw)
        ctx, page, log = new_page(browser, a.width, a.height,
                                  color_scheme="dark" if a.dark else "light", locale=a.locale)
        for i, step in enumerate(steps, 1):
            shot = os.path.join(a.out, f"step-{i:02d}.png")
            entry = {"n": i, "step": step, "ok": True, "screenshot": os.path.basename(shot)}
            try:
                extra = run_step(page, a.url, step)
                settle(page, 400)
                if extra and extra.get("full_page"):
                    entry["screenshot"] = f"step-{i:02d}-{extra['name']}.png"
                    page.screenshot(path=os.path.join(a.out, entry["screenshot"]), full_page=True)
                else:
                    page.screenshot(path=shot)
                entry["url"] = page.url
            except Exception as e:
                entry["ok"] = False
                entry["error"] = str(e).splitlines()[0][:300]
                try:
                    page.screenshot(path=shot)
                except Exception:
                    pass
                failed = entry
                results.append(entry)
                break
            results.append(entry)
        try:
            snapshot = page.evaluate(SNAPSHOT_JS)
        except Exception as e:
            snapshot = {"error": str(e)[:200]}
        ctx.close()
        browser.close()

    report = {"url": a.url, "viewport": [a.width, a.height], "steps": results,
              "passed": failed is None, "failed_step": failed, "on_screen": snapshot, **log}
    save_json(os.path.join(a.out, "run.json"), report)

    for r in results:
        mark = "ok " if r["ok"] else "FAIL"
        print(f"[{mark}] {r['n']:02d} {json.dumps(r['step'], ensure_ascii=False)[:110]}"
              + (f"  -> {r['error']}" if not r["ok"] else "") + f"  ({r['screenshot']})")
    if snapshot and "clickables" in snapshot:
        print(f"\nON SCREEN  {snapshot['url']}  scrollY={snapshot['scrollY']}/{snapshot['pageHeight']}")
        print("TEXT: " + snapshot["visibleText"][:1500])
        print("CLICKABLE (name | tag | center x,y | size | cursor):")
        for c in snapshot["clickables"]:
            flag = "" if c["cursor"] == "pointer" or c["tag"].startswith(("input", "textarea", "select", "label")) else "  <- no pointer cursor"
            print(f"  {c['name'] or '(no name)'} | {c['tag']}{'/' + c['role'] if c['role'] else ''} | "
                  f"{c['x']},{c['y']} | {c['w']}x{c['h']} | {c['cursor']}{' DISABLED' if c['disabled'] else ''}{flag}")
    errs = log["page_errors"] + log["console_errors"]
    if errs:
        print("JS ERRORS: " + " | ".join(errs[:3]))
    return 0 if failed is None else 1


if __name__ == "__main__":
    sys.exit(main())
