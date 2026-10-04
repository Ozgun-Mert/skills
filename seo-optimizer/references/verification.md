# Verification

Run after implementation. Fix what's yours: new or changed frontend files, with a quick yes for
anything that existed before. Report what isn't yours: backend, server config, hosting.

## 1. Serve the site

Ask before installing dependencies (`npm install` changes `node_modules` and possibly the lockfile).

| Stack | Serve a production build |
|---|---|
| Next.js | `npm run build && npm run start -- -p 3000` |
| Astro / Vite / SvelteKit | `npm run build && npm run preview -- --port 4321` |
| Nuxt | `npm run build && node .output/server/index.mjs` (or `npx nuxi preview`) |
| Plain HTML | `python -m http.server 8000 --directory <web-root>` |

Run long-lived servers in the background (Bash `run_in_background`, or the browser pane's
`preview_start` with a `.claude/launch.json` entry). Stop them when you're done.

If no server can run (dependencies not installed and the user declined installing them, or the build
fails for reasons outside your changes), say so plainly. Mark runtime checks as **pending**, and
still run `source_audit.py` to verify the changed source.

## 2. Raw HTML and status codes

```bash
python "SKILL_DIR/scripts/crawl_check.py" http://localhost:3000 --sitemap --max-pages 200 --out seo/crawl.json
python "SKILL_DIR/scripts/sitemap_check.py" http://localhost:3000 --crawl seo/crawl.json --out seo/sitemap-check.json
```

`crawl_check.py` fetches without JS and doesn't auto-follow redirects, so it sees what a crawler's
first pass sees. Read `issues[]` and act on them:

| Issue | Meaning | Who fixes |
|---|---|---|
| `status_5xx`, `status_4xx_linked` | a server error, or an internal link to a missing page | frontend link → you (ask); server → user |
| `redirect_chain`, `redirect_loop` | more than one hop, or a cycle | user (server/config) |
| `soft_404` | an unknown URL returns 200 | user (server/hosting), or the framework's not-found page (you, ask) |
| `missing_title`, `duplicate_title`, `missing_description`, `duplicate_description` | metadata | you |
| `h1_count` ≠ 1 | no H1, or several | you |
| `missing_canonical`, `canonical_mismatch` | canonical absent or pointing elsewhere | you |
| `img_missing_alt` | image without an `alt` attribute | you |
| `orphan` | in the sitemap but not linked from any crawled page | you (add links) |
| `deep_page` | click depth > 3 | you (add links) |
| `placeholder_left` | `{{PLACEHOLDER:` still in the HTML | the user supplies values |
| `thin_html` | very little text in the raw HTML: content probably loads via JS | you (rendering) |
| `noindex_in_sitemap`, `sitemap_url_not_200`, `robots_blocks_sitemap_url`, `robots_blocks_assets` | sitemap or robots conflicts | you |

Run the same two scripts against the **live URL** too, if the user gave one. Live-only problems
(HTTPS, www, CDN redirects) go to the "Backend and server issues" section of the report.

## 3. Mobile protocol (built-in browser)

For every new or changed page, at widths **360, 390, 768, 1280** (`resize_window` with a custom
width/height, e.g. 360×800, 390×844, 768×1024, 1280×800; reset to `desktop` afterwards):

1. Screenshot (scrolling if needed) and look at it. Check that nothing is cut off, overlapping or
   unreadably small.
2. Run this in `javascript_tool`:
   ```js
   (() => {
     const d = document.documentElement;
     const overflow = d.scrollWidth > d.clientWidth;
     const wide = [...document.querySelectorAll('body *')]
       .filter(e => e.getBoundingClientRect().right > d.clientWidth + 1)
       .slice(0, 10).map(e => e.tagName + '.' + [...e.classList].join('.'));
     const small = [...document.querySelectorAll('a,button,[role=button],input,select,textarea')]
       .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.width < 24 || r.height < 24); })
       .slice(0, 15).map(e => (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 40));
     const fontPx = parseFloat(getComputedStyle(document.body).fontSize);
     return { overflow, wide, small, fontPx, h1: document.querySelectorAll('h1').length };
   })()
   ```
   Expect `overflow: false`, `small` empty (or only inline text links inside paragraphs), and
   `fontPx >= 16`.
3. Open the mobile nav and follow one link, to confirm the menu actually works.
4. **Content parity:** the same H1, H2s and key content as at 1280 px. Nothing important should
   be `display:none` on mobile.

Fix overflow and usability bugs in the pages you created or changed. For pre-existing layout problems,
show the screenshot and ask before changing styles.

## 4. Core Web Vitals (deployed URL)

```bash
python "SKILL_DIR/scripts/psi.py" https://example.com/ --out seo/psi-home.json
python "SKILL_DIR/scripts/psi.py" https://example.com/qr-menu --out seo/psi-qr-menu.json
```

The script runs mobile and desktop and reports **field data** (Chrome UX Report, real users, 28 days)
when it exists, otherwise **lab data** (Lighthouse). It always says which one it used. Lab data has
no INP, so it reports Total Blocking Time as a proxy (TBT < 200 ms is roughly comparable).

| Metric | Good | Report as |
|---|---|---|
| LCP | < 2.5 s | pass/fail + the LCP element and its cause |
| INP | < 200 ms | pass/fail (field), or "lab proxy TBT = x ms" |
| CLS | < 0.1 | pass/fail + the shifting elements |

The keyless API shares one global daily quota and is often exhausted (HTTP 429 "Queries per day").
When the user gives you a live URL, also ask whether they have a PageSpeed API key: it's free, at
https://developers.google.com/speed/docs/insights/v5/get-started. Pass it with `--key` or the
`PSI_API_KEY` env var. Never write the key into project files or the state file. Without a key and
with the quota gone, ask the user to run https://pagespeed.web.dev/ for each URL and paste the LCP,
INP and CLS values, and mark the check as pending until they do. **Not deployed:** mark it as pending and do the static checks: hero
image size and format (WebP/AVIF, < ~200 KB), `width`/`height` on images, the LCP image not
lazy-loaded, font loading, render-blocking third-party scripts, large client JS bundles
(page-level `'use client'`).

## 5. UX checklist (report each one as ✅ / ⚠️ / pending)

- Fast (CWV above, or pending)
- Mobile-friendly (section 3)
- HTTPS (live URL starts with https and http redirects to it, otherwise report it)
- Stable layout (CLS, plus image dimensions set)
- Readable (≥ 16 px body text, good contrast, short paragraphs)
- No intrusive popups or interstitials covering the main content on load (cookie banners that are
  small or at the bottom are OK)
- Main content visible immediately (H1 and value proposition above the fold at 390 px)
- Usable navigation (works on mobile, every important page reachable)

## 6. Search Console steps (put these in the final report, in the user's language)

1. Open https://search.google.com/search-console and click **Add property**.
2. Pick **Domain** (covers http/https and www/non-www; needs a DNS TXT record at the domain
   registrar) or **URL prefix** (verify with an HTML file or meta tag: if the user picks the meta tag,
   offer to add it to the layout's `<head>`).
3. After verification: **Indexing → Sitemaps**, enter `sitemap.xml`, then **Submit**.
4. **URL Inspection**: paste each priority URL (listed in the report: home, main keyword pages,
   pricing) and click **Request indexing**.
5. Check **Pages** and **Core Web Vitals** reports after a few days. Indexing takes days to weeks.
