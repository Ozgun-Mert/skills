"""Automatic UI defect finder (Playwright, Chromium). Its output is *hints* for the user persona and a
gate for the final check.

For every route and width it loads the page and measures:
  viewport        missing <meta name=viewport> (phones show a zoomed-out page)   major
  overflow        horizontal page scroll and the element that causes it          major
  cursor          clickable element (semantic or with a JS click handler) whose
                  cursor is not a pointer                                        major (minor: checkbox/radio/select)
  a11y-click      div/span with a click handler but no role/tabindex (no keyboard) major
  sibling-mismatch same-role buttons in one row with different heights or line
                  counts (one label wraps to 2 lines), or stacked full-width
                  buttons with different widths                                  major
  uneven-cards    same-class cards in one row with different heights             minor
  tap-target      interactive target < 24px (WCAG 2.5.8)                         major
                  < 44px on touch widths (< 768)                                 minor
  covered         interactive element in the first screen hidden under another
                  element (cookie bar, sticky footer, chat bubble)               major
  clipped         text cut off by its box (overflow hidden, no ellipsis/clamp)   major
  spill           nowrap text spilling out of its box                            minor
  image           broken image (major), missing alt (minor), stretched (minor)
  contrast        text contrast below WCAG AA (< 3:1 major, else minor)
  no-name         icon-only button/link without an accessible name               minor
  headings        not exactly one <h1>, or a skipped heading level               minor
  fonts/colors    > 3 font families or > 10 font sizes in use                    minor
  stuck-invisible text that was in view during the scroll-through but never became visible
                  (an entrance animation that never fires; common with scroll-triggered
                  React Bits / GSAP reveals)                                     major
  webgl-mobile    a large canvas (likely a WebGL background) on a touch width, or
                  two large canvases in view at once                             minor
  http/js         route status >= 400 (blocker), page errors (major), console
                  errors / failed requests (major)
Also reports the word count per page and per screen (wordiness), and the font families, sizes and
colors in use.

Usage:
  python ui_audit.py --url http://localhost:5173 --routes "/,/menu" --out DESIGN/.work/reviews/round-1/audit
                     [--routes-file f] [--widths 360,390,768,1280,1440] [--annotate] [--dark]
                     [--fail-on blocker|major|minor] [--reduced-motion] [--no-reveal]
Before measuring, it scrolls through each page once (common.reveal_all), so scroll-triggered entrance
animations have run; --no-reveal skips that. --reduced-motion audits with prefers-reduced-motion: reduce,
to check that every piece of content still shows without animation.
Writes <out>/audit.json, <out>/audit.md and, with --annotate, <out>/annotated/<route>@<w>.png
(numbered red boxes = the issues in audit.md). Exit 1 when --fail-on is given and an issue at that
severity or worse exists.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (join_url, launch, route_expect, new_page, parse_routes, parse_widths, require_playwright,  # noqa: E402
                    reveal_all, save_json, settle, slug, utf8_stdout, write_text)

SEV_ORDER = {"blocker": 0, "major": 1, "minor": 2}

# Records elements that get click-like listeners (Vue, Angular, Svelte 4, vanilla, Alpine…).
INIT_JS = r"""
(() => {
  const orig = EventTarget.prototype.addEventListener;
  const set = new WeakSet();
  Object.defineProperty(window, '__uiAuditClick', {value: set});
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    try {
      if (this instanceof Element && /^(click|mousedown|mouseup|pointerdown|pointerup|touchend)$/.test(type)) set.add(this);
    } catch (e) {}
    return orig.call(this, type, fn, opts);
  };
})();
"""

AUDIT_JS = r"""
(opts) => {
  // mobile emulation widens innerWidth to fit overflowing content, so use the configured width
  const vw = opts.width || innerWidth, vh = opts.height || innerHeight, touch = vw < 768;
  const issues = [];
  const cs = el => getComputedStyle(el);
  const rectOf = el => { const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height)}; };
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const s = cs(e);
      if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) return false;
      if (s.clipPath && s.clipPath.startsWith('inset(50%')) return false;
    }
    const s = cs(el);
    if (s.clip && s.clip.startsWith('rect(0') ) return false;
    return true;
  };
  const describe = el => {
    const parts = [];
    for (let e = el, i = 0; e && e.nodeType === 1 && i < 4 && e !== document.body; e = e.parentElement, i++) {
      let p = e.tagName.toLowerCase();
      if (e.id && !/\d{3,}/.test(e.id)) { parts.unshift(p + '#' + e.id); break; }
      const cls = [...e.classList].filter(c => c.length < 30 && !/[:\[\]\/]/.test(c)).slice(0, 2);
      if (cls.length) p += '.' + cls.join('.');
      const sib = e.parentElement ? [...e.parentElement.children].filter(c => c.tagName === e.tagName) : [];
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(e) + 1})`;
      parts.unshift(p);
    }
    return parts.join(' > ');
  };
  const label = el => (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('alt') ||
                       el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 50);
  const add = (check, severity, el, detail, extra) => issues.push(Object.assign(
      {check, severity, selector: el ? describe(el) : '', text: el ? label(el) : '', detail,
       rect: el ? rectOf(el) : null}, extra || {}));

  const hasHandler = el => {
    if (el.onclick || (window.__uiAuditClick && window.__uiAuditClick.has(el)) || el.__click) return true;
    for (const k in el) {
      if (k.startsWith('__reactProps$')) { const p = el[k] || {}; if (p.onClick || p.onMouseDown || p.onPointerDown) return true; }
    }
    if (el.l && typeof el.l === 'object' && Object.keys(el.l).some(k => k.startsWith('click'))) return true; // preact
    return false;
  };
  const SEM = 'a[href],button,summary,select,input:not([type=hidden]),textarea,label[for],[role=button],[role=link],' +
              '[role=tab],[role=menuitem],[role=option],[role=switch],[role=checkbox],[role=radio]';
  const isSemantic = el => el.matches(SEM);
  const textInput = el => el.matches('textarea,input:not([type]),input[type=text],input[type=email],input[type=search],' +
      'input[type=password],input[type=tel],input[type=url],input[type=number],input[type=date],input[type=time]');
  const huge = el => { const r = el.getBoundingClientRect(); return r.width * r.height > 0.4 * vw * vh; };

  if (touch && !document.querySelector('meta[name=viewport]'))
    add('viewport', 'major', null, 'no <meta name="viewport" content="width=device-width, initial-scale=1">: phones render a zoomed-out desktop page');

  // ---- overflow (without a viewport meta every page is 980px wide; that is the viewport issue, not this one)
  const docW = document.documentElement.scrollWidth;
  if (docW > vw + 1 && !(touch && !document.querySelector('meta[name=viewport]'))) {
    const culprits = [];
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right <= vw + 1 || r.width < 1 || !visible(el)) continue;
      let contained = false, parentOver = false;
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const ps = cs(p);
        if (/(auto|scroll|hidden|clip)/.test(ps.overflowX)) { contained = true; break; }
      }
      const pr = el.parentElement && el.parentElement.getBoundingClientRect();
      if (pr && pr.right > vw + 1) parentOver = true;
      if (!contained && !parentOver) culprits.push(el);
      if (culprits.length >= 4) break;
    }
    if (!culprits.length) add('overflow', 'major', null, `page is ${docW}px wide in a ${vw}px viewport`);
    for (const el of culprits) add('overflow', 'major', el,
        `page scrolls sideways: page ${docW}px > viewport ${vw}px; this element ends at ${Math.round(el.getBoundingClientRect().right)}px`);
  }

  // ---- collect interactive elements
  const all = [...document.body.querySelectorAll('*')];
  const interactive = [];
  for (const el of all) {
    if (!(isSemantic(el) || hasHandler(el))) continue;
    if (el === document.body || huge(el) || !visible(el)) continue;
    interactive.push(el);
  }

  // ---- cursor, keyboard access, accessible name
  for (const el of interactive) {
    const s = cs(el);
    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
    if (disabled || textInput(el)) continue;
    if (el.tagName === 'LABEL') { const c = el.control; if (!c || textInput(c)) continue; }
    // a handler on a wrapper whose own clickable child carries the pointer is fine
    if (!isSemantic(el) && el.querySelector(SEM)) continue;
    if (s.cursor !== 'pointer') {
      const minor = el.matches('input[type=checkbox],input[type=radio],select,input[type=range],input[type=color],input[type=file],label');
      add('cursor', minor ? 'minor' : 'major', el, `clickable but cursor is "${s.cursor}", not "pointer"`);
    }
    if (!isSemantic(el) && !el.hasAttribute('tabindex')) {
      add('a11y-click', 'major', el, `<${el.tagName.toLowerCase()}> has a click handler but no role/tabindex: unreachable by keyboard and screen readers (use <button> or <a>)`);
    }
    if (el.matches('a[href],button,[role=button],[role=link]') && !label(el) &&
        !el.getAttribute('aria-labelledby') && !(el.querySelector('img[alt]:not([alt=""]),svg title'))) {
      add('no-name', 'minor', el, 'icon-only control without an accessible name (add aria-label)');
    }
  }

  // ---- tap targets
  for (const el of interactive) {
    if (el.tagName === 'LABEL' || el.disabled) continue;
    const s = cs(el);
    if (el.tagName === 'A' && s.display === 'inline') {
      const p = el.parentElement;
      const txt = p ? [...p.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) : false;
      if (txt) continue; // inline link inside running text is exempt
    }
    const r = el.getBoundingClientRect();
    const m = Math.min(r.width, r.height);
    if (m < 24) add('tap-target', 'major', el, `target is ${Math.round(r.width)}x${Math.round(r.height)}px (< 24px, WCAG 2.5.8)`);
    else if (touch && m < 44 && !el.matches('input[type=checkbox],input[type=radio]'))
      add('tap-target', 'minor', el, `target is ${Math.round(r.width)}x${Math.round(r.height)}px on a touch screen (< 44px)`);
  }

  // ---- covered (first screen only; scrolled content under a sticky header is normal)
  if (scrollY === 0) {
    for (const el of interactive) {
      const r = el.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x >= vw || y >= vh) continue;
      const hit = document.elementFromPoint(x, y);
      if (!hit || hit === el || el.contains(hit)) continue;
      if (hit.tagName === 'LABEL' && hit.control === el) continue;
      if (hit.contains(el) && cs(el).pointerEvents === 'none') continue;
      let cover = hit;
      for (let e = hit; e && e !== document.body; e = e.parentElement) {
        const p = cs(e).position; if (p === 'fixed' || p === 'sticky' || p === 'absolute') { cover = e; break; }
      }
      if (cover.contains(el)) continue;
      add('covered', 'major', el, `center is covered by ${describe(cover)} ("${label(cover).slice(0, 30)}")`);
    }
  }

  // ---- sibling mismatch (buttons) and uneven cards
  const buttonLike = el => {
    if (el.matches('button,input[type=submit],input[type=button],[role=button]')) return true;
    if (el.tagName !== 'A') return false;
    const s = cs(el);
    const bg = s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent';
    const border = parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none';
    return (bg || border) && parseFloat(s.paddingLeft) >= 8 && s.display !== 'inline';
  };
  const lines = el => {
    // count rendered text lines (box height lies when flex stretches siblings to the same height)
    const tops = new Set();
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = w.nextNode())) {
      if (!t.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(t);
      for (const rc of r.getClientRects()) if (rc.width > 1) tops.add(Math.round(rc.top / 4));
    }
    if (el.tagName === 'INPUT') return 1;
    return Math.max(1, tops.size);
  };
  const buttons = interactive.filter(buttonLike).filter(el => el.innerText && el.innerText.trim());
  const groups = new Map();
  for (const el of buttons) {
    // group by the nearest ancestor that holds 2+ of these buttons (max 3 levels up)
    let g = el.parentElement;
    for (let i = 0; i < 3 && g; i++, g = g.parentElement) {
      if (buttons.filter(b => b !== el && g.contains(b)).length) break;
    }
    if (!g) continue;
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(el);
  }
  for (const [g, els] of groups) {
    if (els.length < 2) continue;
    const rows = [];
    for (const el of els) {
      const r = el.getBoundingClientRect(), cy = r.top + r.height / 2;
      const row = rows.find(rw => Math.abs(rw.cy - cy) < Math.max(r.height, rw.h) / 2);
      if (row) row.items.push(el); else rows.push({cy, h: r.height, items: [el]});
    }
    for (const row of rows) {
      if (row.items.length < 2) continue;
      const hs = row.items.map(e => e.getBoundingClientRect().height), ls = row.items.map(lines);
      if (Math.max(...hs) - Math.min(...hs) > 3 || Math.max(...ls) !== Math.min(...ls)) {
        const tall = Math.max(...ls) !== Math.min(...ls) ? row.items[ls.indexOf(Math.max(...ls))]
                                                         : row.items[hs.indexOf(Math.max(...hs))];
        add('sibling-mismatch', 'major', tall,
          'buttons side by side differ: ' + row.items.map((e, i) => `"${label(e)}" ${Math.round(hs[i])}px/${ls[i]} line${ls[i] > 1 ? 's' : ''}`).join(', '));
      }
    }
    // stacked full-width-ish buttons with different widths
    const col = els.filter(e => e.getBoundingClientRect().width > 0.6 * g.getBoundingClientRect().width);
    if (col.length >= 2 && rows.length >= 2) {
      const ws = col.map(e => e.getBoundingClientRect().width);
      if (Math.max(...ws) - Math.min(...ws) > 8)
        add('sibling-mismatch', 'minor', col[ws.indexOf(Math.min(...ws))],
          'stacked buttons have different widths: ' + col.map((e, i) => `"${label(e)}" ${Math.round(ws[i])}px`).join(', '));
    }
  }
  for (const c of all) {
    const s = cs(c);
    if (!(s.display.includes('grid') || s.display.includes('flex')) || c.children.length < 2) continue;
    if (s.display.includes('flex') && s.flexDirection.startsWith('column')) continue;
    const kids = [...c.children].filter(k => visible(k) && k.className && typeof k.className === 'string');
    const sig = k => k.tagName + '.' + [...k.classList].sort().join('.');
    const bySig = new Map();
    for (const k of kids) { const key = sig(k); if (!bySig.has(key)) bySig.set(key, []); bySig.get(key).push(k); }
    for (const [, ks] of bySig) {
      if (ks.length < 2) continue;
      const ks2 = ks.filter(k => k.getBoundingClientRect().height > 60 && k.getBoundingClientRect().width > 100);
      if (ks2.length < 2) continue;
      const tops = new Map();
      for (const k of ks2) { const t = Math.round(k.getBoundingClientRect().top / 4); if (!tops.has(t)) tops.set(t, []); tops.get(t).push(k); }
      for (const [, row] of tops) {
        if (row.length < 2) continue;
        const hs = row.map(k => k.getBoundingClientRect().height);
        if (Math.max(...hs) - Math.min(...hs) > 8)
          add('uneven-cards', 'minor', c, `cards in one row have different heights: ${hs.map(Math.round).join(' / ')}px`);
      }
    }
  }

  // ---- text clipping / spilling, contrast, fonts
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (top, bot) => { const a = top[3]; return [top[0] * a + bot[0] * (1 - a), top[1] * a + bot[1] * (1 - a), top[2] * a + bot[2] * (1 - a), 1]; };
  const bgOf = el => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) {
      const s = cs(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null; // over image/gradient: can't judge
      const c = parse(s.backgroundColor);
      if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break; }
    }
    let base = [255, 255, 255, 1];
    for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base);
    return base;
  };
  const families = new Map(), sizes = new Set(), colors = new Set(), contrastSeen = new Set();
  let textEls = 0;
  for (const el of all) {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!own || !visible(el)) continue;
    if (++textEls > 1500) break;
    const s = cs(el);
    const fam = s.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    families.set(fam, (families.get(fam) || 0) + 1);
    sizes.add(s.fontSize); colors.add(s.color);
    // clipped
    const hidden = /(hidden|clip)/.test(s.overflowX) || /(hidden|clip)/.test(s.overflowY);
    if (hidden && s.textOverflow !== 'ellipsis' && s.webkitLineClamp === 'none' && !el.matches('input,textarea,select')) {
      if (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 3)
        add('clipped', 'major', el, `text is cut off (content ${el.scrollWidth}x${el.scrollHeight}px in a ${el.clientWidth}x${el.clientHeight}px box)`);
    } else if (!hidden && s.whiteSpace.includes('nowrap') && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
      add('spill', 'minor', el, `nowrap text spills out of its box (${el.scrollWidth}px text in ${el.clientWidth}px)`);
    }
    // contrast
    if (el.disabled || el.closest('[aria-disabled=true],[disabled]')) continue;
    const fg = parse(s.color); const bg = bgOf(el);
    if (!fg || !bg) continue;
    const fgc = blend(fg, bg);
    const L1 = lum(fgc), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
    const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    if (ratio < need) {
      const key = s.color + '|' + bg.join(',') + '|' + large;
      if (contrastSeen.has(key)) continue; contrastSeen.add(key);
      add('contrast', ratio < 3 ? 'major' : 'minor', el,
          `contrast ${ratio.toFixed(2)}:1 (needs ${need}:1) text ${s.color} on rgb(${bg.slice(0, 3).map(Math.round).join(', ')})`);
    }
  }
  const famList = [...families.entries()].sort((a, b) => b[1] - a[1]);
  if (famList.length > 3) add('fonts', 'minor', null, `${famList.length} font families in use: ${famList.map(f => f[0]).join(', ')}`);
  if (sizes.size > 10) add('fonts', 'minor', null, `${sizes.size} different font sizes in use: ${[...sizes].sort((a, b) => parseFloat(a) - parseFloat(b)).join(' ')}`);

  // ---- big canvases (WebGL backgrounds, 3D galleries)
  const canv = [...document.querySelectorAll('canvas')].filter(c => {
    const r = c.getBoundingClientRect();
    return visible(c) && r.width * r.height > 0.3 * vw * vh && r.bottom > 0 && r.top < vh;
  });
  if (touch && canv.length) add('webgl-mobile', 'minor', canv[0],
    `large canvas (${Math.round(canv[0].getBoundingClientRect().width)}x${Math.round(canv[0].getBoundingClientRect().height)}px) on a ${vw}px touch screen: swap the WebGL background for a static gradient on mobile`);
  else if (canv.length > 1) add('webgl-mobile', 'minor', canv[1], `${canv.length} large canvases in view at once: keep one WebGL scene per viewport`);

  // ---- images
  for (const img of document.images) {
    if (!visible(img)) continue;
    if (img.complete && img.naturalWidth === 0 && img.currentSrc) add('image', 'major', img, `broken image: ${img.currentSrc.slice(0, 120)}`);
    if (img.getAttribute('alt') === null) add('image', 'minor', img, 'image without alt attribute (use alt="" if decorative)');
    const s = cs(img);
    if (img.naturalWidth && s.objectFit === 'fill') {
      const r = img.getBoundingClientRect();
      const want = img.naturalWidth / img.naturalHeight, got = r.width / r.height;
      if (Math.abs(got - want) / want > 0.05) add('image', 'minor', img, `image is stretched (natural ratio ${want.toFixed(2)}, shown ${got.toFixed(2)}); use object-fit: cover`);
    }
  }

  // ---- headings
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible);
  const h1 = hs.filter(h => h.tagName === 'H1').length;
  if (h1 !== 1) add('headings', 'minor', null, `${h1} visible <h1> elements (should be exactly 1)`);
  for (let i = 1; i < hs.length; i++) {
    const a = +hs[i - 1].tagName[1], b = +hs[i].tagName[1];
    if (b > a + 1) { add('headings', 'minor', hs[i], `heading level jumps from h${a} to h${b}`); break; }
  }

  // ---- wordiness
  const words = t => (t.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) || []).length;
  const bodyText = document.body.innerText || '';
  let firstScreen = '';
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const p = n.parentElement; if (!p || !n.textContent.trim()) continue;
    const r = p.getBoundingClientRect();
    if (r.bottom > 0 && r.top < vh && visible(p)) firstScreen += ' ' + n.textContent;
  }
  const pageH = document.documentElement.scrollHeight;
  const stats = {words_total: words(bodyText), words_first_screen: words(firstScreen),
                 screens: +(pageH / vh).toFixed(1), page_height: pageH,
                 words_per_screen: Math.round(words(bodyText) / Math.max(1, pageH / vh)),
                 font_families: famList.slice(0, 8), font_sizes: [...sizes].length,
                 text_colors: [...colors].slice(0, 12), interactive: interactive.length, text_elements: textEls};
  return {issues, stats};
}
"""

ANNOTATE_JS = r"""
(boxes) => {
  const layer = document.createElement('div');
  layer.id = '__ui_audit_layer';
  layer.style.cssText = 'position:absolute;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none';
  for (const b of boxes) {
    const d = document.createElement('div');
    d.style.cssText = `position:absolute;left:${b.x - 2}px;top:${b.y - 2}px;width:${b.w + 4}px;height:${b.h + 4}px;` +
      `border:2px solid ${b.sev === 'minor' ? '#f59e0b' : '#e11d48'};box-sizing:border-box;border-radius:3px`;
    const t = document.createElement('span');
    t.textContent = b.n;
    t.style.cssText = `position:absolute;left:-2px;top:-18px;background:${b.sev === 'minor' ? '#f59e0b' : '#e11d48'};` +
      'color:#fff;font:bold 11px/16px sans-serif;padding:0 4px;border-radius:3px';
    d.appendChild(t); layer.appendChild(d);
  }
  document.body.appendChild(layer);
}
"""


def issue_key(it):
    # numbers differ per width ("980px wide in a 360px viewport"), so they don't split an issue
    return (it["route"], it["check"], it["selector"], re.sub(r"\d+(\.\d+)?", "#", it["detail"].split(":")[0]))


def merge(issues):
    """Same check + selector + detail on several widths becomes one issue with a list of widths."""
    out = {}
    for it in issues:
        key = issue_key(it)
        if key in out:
            if it["width"] not in out[key]["widths"]:
                out[key]["widths"].append(it["width"])
            if SEV_ORDER[it["severity"]] < SEV_ORDER[out[key]["severity"]]:
                out[key]["severity"] = it["severity"]
        else:
            d = dict(it)
            d["widths"] = [d.pop("width")]
            d.pop("rect", None)
            out[key] = d
    return sorted(out.values(), key=lambda d: (SEV_ORDER[d["severity"]], d["route"], d["check"]))


def to_markdown(url, merged, pages):
    counts = {s: sum(1 for i in merged if i["severity"] == s) for s in SEV_ORDER}
    lines = [f"# UI audit: {url}", "",
             f"**{counts['blocker']} blocker · {counts['major']} major · {counts['minor']} minor**", "",
             "Hints from automatic measurement. Confirm each one on the screenshots before reporting it.", ""]
    for sev in SEV_ORDER:
        rows = [i for i in merged if i["severity"] == sev]
        if not rows:
            continue
        lines += [f"## {sev.capitalize()} ({len(rows)})", "", "| # | Route | Widths | Check | Element | What |",
                  "|---|---|---|---|---|---|"]
        for i in rows:
            el = (i["selector"] or "page") + (f' "{i["text"]}"' if i["text"] else "")
            lines.append(f"| {i['id']} | `{i['route']}` | {','.join(map(str, sorted(i['widths'])))} | {i['check']} | "
                         f"`{el.replace('|', '/')[:90]}` | {i['detail'].replace('|', '/')} |")
        lines.append("")
    lines += ["## Page stats", "", "| Route | Width | Status | Words | 1st screen | Words/screen | Screens | Fonts |",
              "|---|---|---|---|---|---|---|---|"]
    for p in pages:
        s = p.get("stats") or {}
        fams = ", ".join(f[0] for f in s.get("font_families", [])[:3])
        lines.append(f"| `{p['route']}` | {p['width']} | {p.get('status')} | {s.get('words_total', '-')} | "
                     f"{s.get('words_first_screen', '-')} | {s.get('words_per_screen', '-')} | {s.get('screens', '-')} | {fams} |")
    return "\n".join(lines) + "\n"


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--routes", default="")
    ap.add_argument("--routes-file")
    ap.add_argument("--widths", default="")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--out", required=True)
    ap.add_argument("--annotate", action="store_true")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--wait", type=int, default=800)
    ap.add_argument("--fail-on", choices=list(SEV_ORDER))
    ap.add_argument("--reduced-motion", action="store_true")
    ap.add_argument("--no-reveal", action="store_true")
    a = ap.parse_args()

    routes = parse_routes(a.routes, a.routes_file)
    widths = parse_widths(a.widths)
    os.makedirs(a.out, exist_ok=True)
    sync_playwright = require_playwright()
    raw, pages = [], []
    with sync_playwright() as pw:
        browser = launch(pw)
        for width in widths:
            for route_line in routes:
                route, expected = route_expect(route_line)
                ctx, page, log = new_page(browser, width, a.height, color_scheme="dark" if a.dark else "light",
                                          reduced_motion="reduce" if a.reduced_motion else "no-preference")
                page.add_init_script(INIT_JS)
                info = {"route": route, "width": width, "status": None}
                found = []
                try:
                    resp = page.goto(join_url(a.url, route), wait_until="domcontentloaded", timeout=30000)
                    info["status"] = resp.status if resp else None
                    settle(page, a.wait)
                    stuck = [] if a.no_reveal else reveal_all(page, track=True)
                    res = page.evaluate(AUDIT_JS, {"width": width, "height": a.height})
                    found, info["stats"] = res["issues"], res["stats"]
                    for el in stuck:
                        found.append({"check": "stuck-invisible", "severity": "major", "selector": el["selector"],
                                      "text": el["text"], "rect": el["rect"],
                                      "detail": "text was on screen during the scroll-through but never became "
                                                "visible (entrance animation never fired or starts hidden)"})
                except Exception as e:
                    found.append({"check": "http", "severity": "blocker", "selector": "", "text": "",
                                  "detail": f"page failed to load: {str(e).splitlines()[0][:200]}", "rect": None})
                if expected and info["status"] != expected:
                    found.append({"check": "http", "severity": "major", "selector": "", "text": "",
                                  "detail": f"route should return HTTP {expected} but returns {info['status']}",
                                  "rect": None})
                elif info["status"] and info["status"] >= 400 and not expected:
                    found.append({"check": "http", "severity": "blocker", "selector": "", "text": "",
                                  "detail": f"route returns HTTP {info['status']}", "rect": None})
                if info["status"] and info["status"] >= 400:
                    # the failing document itself would otherwise be reported again as a failed request
                    # and a console error
                    doc = join_url(a.url, route)
                    log["failed_requests"] = [r for r in log["failed_requests"] if doc not in r]
                    log["console_errors"] = [c for c in log["console_errors"]
                                             if "Failed to load resource" not in c]
                if log["page_errors"]:
                    found.append({"check": "js", "severity": "major", "selector": "", "text": "",
                                  "detail": "uncaught JS error: " + log["page_errors"][0], "rect": None})
                if log["console_errors"]:
                    found.append({"check": "js", "severity": "major", "selector": "", "text": "",
                                  "detail": "console error: " + log["console_errors"][0], "rect": None})
                for fr in log["failed_requests"][:3]:
                    found.append({"check": "http", "severity": "major", "selector": "", "text": "",
                                  "detail": "failed request: " + fr, "rect": None})
                for f in found:
                    f["route"], f["width"] = route, width
                raw.extend(found)
                info["log"] = log
                pages.append(info)
                if a.annotate:
                    pages[-1]["_page"] = (ctx, page, found)  # drawn after merge, when issue ids exist
                else:
                    ctx.close()

        merged = merge(raw)
        for n, it in enumerate(merged, 1):
            it["id"] = n
        if a.annotate:
            os.makedirs(os.path.join(a.out, "annotated"), exist_ok=True)
            index = {}
            for i in merged:
                index.setdefault(issue_key(i), i)
            for p in pages:
                ctx, page, found = p.pop("_page")
                boxes = []
                for f in found:
                    if f.get("rect"):
                        m = index.get(issue_key(f))
                        boxes.append({**f["rect"], "sev": f["severity"], "n": m["id"] if m else "?"})
                try:
                    if boxes:
                        page.evaluate(ANNOTATE_JS, boxes)
                    h = page.evaluate("document.documentElement.scrollHeight")
                    path = os.path.join(a.out, "annotated", f"{slug(p['route'])}@{p['width']}.png")
                    if h > 6000:
                        page.screenshot(path=path, full_page=True, clip={"x": 0, "y": 0, "width": p["width"], "height": 6000})
                    else:
                        page.screenshot(path=path, full_page=True)
                except Exception:
                    pass
                ctx.close()
        browser.close()

    for p in pages:
        p.pop("_page", None)
    save_json(os.path.join(a.out, "audit.json"), {"url": a.url, "issues": merged, "pages": pages})
    write_text(os.path.join(a.out, "audit.md"), to_markdown(a.url, merged, pages))
    counts = {s: sum(1 for i in merged if i["severity"] == s) for s in SEV_ORDER}
    print(f"{counts['blocker']} blocker, {counts['major']} major, {counts['minor']} minor "
          f"({len(routes)} routes x {len(widths)} widths) -> {os.path.join(a.out, 'audit.md')}")
    for i in merged[:25]:
        widths = ",".join(map(str, sorted(i["widths"])))
        text = f'"{i["text"][:30]}"' if i["text"] else ""
        print(f"  #{i['id']} [{i['severity']}] {i['route']} @{widths} {i['check']}: "
              f"{i['selector'][:60]} {text} - {i['detail'][:140]}")
    if len(merged) > 25:
        print(f"  ... {len(merged) - 25} more in audit.md")
    if a.fail_on:
        worst = SEV_ORDER[a.fail_on]
        if any(SEV_ORDER[i["severity"]] <= worst for i in merged):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
