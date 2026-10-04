---
name: optimize-seo
description: People-first SEO for any website project. Finds and researches keywords (live Google top-3), maps every search intent to the right page, gets the user's approval, then writes frontend pages (landing, keyword pages, blog posts, FAQ, about, contact, pricing, legal) and technical SEO (titles/meta, JSON-LD, robots.txt, sitemap.xml, internal links, crawlable server rendering, mobile layout, Core Web Vitals). Use whenever the user types /optimize-seo or /optimize-SEO (with or without keywords such as ['qr menü', 'karekod menü']), or asks to improve SEO, rank higher on Google or any search engine, optimize a site or landing page for specific words, make a website show up in search results, add or fix a sitemap, robots.txt, meta tags or structured data, or write SEO blog posts/pages for their product or personal site, even if they never say "SEO". Works on Next.js, Astro, Nuxt, SvelteKit, Remix, React/Vue SPAs, plain HTML and empty folders. Not for paid search ads (Google Ads, SEM, PPC) or social-media marketing.
argument-hint: "['word one', 'word two'] (optional)"
---

# /optimize-seo

Input: `$ARGUMENTS`, an optional list of words to optimize for. Accept any of these forms:
`['qr menü', 'karekod menü']` · `qr menü, karekod menü` · `"qr menü" "karekod menü"` · empty.
Keep keywords exactly as typed (Turkish and other non-ASCII letters included). Transliterate only
for URL slugs (`karekod menü` → `/karekod-menu`; see `references/technical-seo.md`).

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded. Scripts are
`python "SKILL_DIR/scripts/<name>.py"` (standard library only, no installs). Read each reference file
when you reach the phase that points to it, not all up front.

**The goal is for the website to rank, not for the landing page to rank for every word.** A search
for "nişantaşı arabuluculuk" can be answered best by the About or Contact page. A landing page that
tries to match every phrase becomes a wall of text people bounce from. Bouncing hurts rankings and
conversions both, so spread intents across the right pages and keep the landing page short.

From here on, **words** means the user's words plus any words the user approved from your proposals.

## Hard rules

These exist because the user owns the site, the product and the legal risk. You are a collaborator
proposing changes, not an autopilot.

1. **Ask, don't guess.** An unclear city, audience (B2B or B2C), plan, feature, price, language or
   country changes what you write. Stop and ask. Use AskUserQuestion for choices (2–4 options) and
   plain questions for facts. Batch related questions into one message.
2. **Every website change needs approval first.** That covers new pages, edits to existing pages,
   and visual changes. Approval is per change set: a "yes" to the page plan is not a "yes" to
   restyling the hero. The only automatic edit is the `.gitignore` line in Phase 0.
3. **Never touch backend code.** Frontend only. If a page needs API data, ask for the endpoint,
   request/response shape, auth and caching. If the user declines, use static content or
   placeholders and keep going.
4. **Never copy competitor content.** Take topics, angles and structure from *relevant* results
   only. Every sentence you write is original and fits this project.
5. **Never fabricate** statistics, testimonials, reviews, ratings, client logos, awards, author bios,
   legal facts or product features. Use `{{PLACEHOLDER: snake_case_name}}` and ask. Invented facts
   can mislead customers and expose the owner legally. A visible placeholder is safe.
6. **Never solve or bypass a CAPTCHA.** If Google blocks you, switch to WebSearch for the rest of
   the run and tell the user the results may differ from real Google rankings.
7. **Keep the landing page lean.** One main commercial intent, then links out to the rest.
8. **Don't touch git.** No branches, commits, stashes, `git add` or `git rm`. Read-only commands
   (`git status`, `git ls-files`, `git check-ignore`) are fine. Editing `.gitignore` is a file edit,
   and keeping `/seo/` in it is required.
9. **Language:** talk to the user in the language they use. Write site content in the confirmed
   target language(s).
10. **Leave visuals alone** (animations, colors, layout) unless they hurt SEO noticeably, e.g. a
    huge hero image causing bad LCP, layout shift, or content that only appears after JS. In that
    case explain the impact and ask before changing anything.

## The approval formats (use these exact shapes)

**Page plan.** One table, one row per page. The user answers every row in one reply:

```
I am going to add / change these pages. Reply per row: yes / no / yes but change …

| # | Path | New/Existing | Page type | Primary keyword | Secondary keywords | Intent | Missing info → placeholder |
|---|------|--------------|-----------|-----------------|--------------------|--------|----------------------------|
| 1 | /qr-menu | New | Keyword page | qr menü | karekod menü, dijital menü | commercial | — |
| 2 | /pricing | New | Pricing | qr menü fiyatları | qr menü ücretleri | pricing | plan prices → {{PLACEHOLDER: price_basic_monthly}} |
```

Ask follow-up questions only for rows marked "change".

**Legal pages.** Ask once per legal page with exactly three options: **Yes** · **Yes with banner** ·
**No** (details in `references/professional-pages.md`).

**Final go-ahead before editing.** List every file you will create or modify (path + one-line
purpose) and wait for a yes.

## Phase 0: Preflight (read only, except the `.gitignore` line)

1. **State.** If `seo/seo-plan.json` exists, read it and briefly summarize what earlier runs did:
   pages, open placeholders, rejected rows and pending checks. Don't re-ask answered questions, and
   don't plan a page whose primary keyword is already owned by another page. Schema:
   `references/state-schema.md`.
2. **Gitignore the state folder**, automatically, before writing anything into `seo/`:
   `python "SKILL_DIR/scripts/ensure_gitignore.py" --root .`
   It adds `/seo/` once under `# optimize-seo state (local only)`, creating `.gitignore` if it's
   missing. If the folder is a git repo, it verifies with `git check-ignore` and reports files already
   tracked. Act on its JSON:
   - `"collision": true`: a root `seo/` folder already holds app code or content. Ask the user for
     another state folder name, re-run with `--state-dir <name>`, and record it in the state file.
   - `"tracked_files"` not empty: tell the user to run `git rm -r --cached seo` themselves.
3. **Understand the project.** Run `python "SKILL_DIR/scripts/source_audit.py" --root .` for a
   structured inventory: stack, router, routes, metadata, robots/sitemap, JSON-LD, page-level
   `'use client'`, JS-only navigation, images without `alt`, H1 counts, placeholders, and detected
   backend paths. Then read the actual pages, components, copy, README and package.json yourself. The
   script finds things; it doesn't understand the product.
4. **Map the backend boundary.** Treat as read-only: `app/api/**`, `pages/api/**`, `server/**`,
   `src/server/**`, DB/ORM code (prisma, drizzle, models), server actions that write data, auth,
   workers, `.env*`. If something is ambiguous (`middleware.ts`, `next.config.*` redirects and
   headers, `vercel.json`, `netlify.toml`, `nginx.conf`), ask before touching it.
5. **Live URL.** Ask for the production domain if one exists. Canonicals, absolute sitemap URLs,
   status checks and PageSpeed all need it. If it is live, also ask for an optional free PageSpeed
   API key, because the keyless quota is often exhausted (see `references/verification.md`). If the
   site isn't live, use `{{PLACEHOLDER: site_url}}` and record it as open.

## Phase 1: Words

Pick the mode:

| Mode | When | Do this |
|---|---|---|
| **A** | words given | Read the project, then expand the words with close variants: synonyms, local spellings (`qr menü` / `qr menu` / `karekod menü`), long-tail and local forms. Show the expanded list with one reason per added word. The user can add or remove words. |
| **B** | no words, project has content | Read the whole frontend and propose a prioritized word list (about 5–15), each with a reason tied to what the product actually does. Ask for approval and offer to expand. |
| **C** | no words, empty folder or no site | Interview first: what the product or person is, audience, location or market, languages, competitors, business model, scope, and which pages they want. Then propose words. If words were given but the folder is empty, still run this interview, because the project facts are unknown. |

Approval gate: the final word list, plus target language(s), country, and city or region if the
business is local. If the site will have more than one language, confirm that now, because it
changes URLs (`hreflang`).

## Phase 2: Research (read `references/research.md`)

For every word, collect the **top 3 organic results** from Google in the target locale, using the
built-in browser first and WebSearch as the fallback. For each result, record the URL, title, H1/H2
outline, page type, intent served, strengths, **what it's missing**, and a **relevance verdict**
for our project. Also record People Also Ask questions and related searches. Save everything to
`seo/research/<keyword-slug>.md`. Take inspiration from relevant results only, and copy nothing.

## Phase 3: Keyword map (read `references/keyword-mapping.md`)

Turn each word into sub-keywords, tag each with an intent (informational, commercial,
transactional/pricing, local, navigational/brand), and assign each to the page that best answers it.
Typical homes: informational → `/blog/<slug>` or FAQ · commercial → landing page or a keyword page
such as `/qr-menu` · pricing → `/pricing` · local or brand → `/about` / `/contact`. Prefer improving
an existing page over creating a new one. Each page owns one primary keyword, and no two pages share
a primary keyword. No doorway pages: never make near-identical pages that differ only by a city or
a synonym.

Then show the **page plan table** (format above). Pages the user rejects are gone. Record them so
later runs don't propose them again.

## Phase 4: Content brief and fact check (read `references/content.md`)

For each approved page, write a short brief: the reader's question, the angle the top-3 results miss,
the H1/H2/H3 outline, internal links in and out, and the CTA. Before writing copy:
- List every product claim the copy will make and ask the user to confirm each one. A feature you
  promise but the product lacks costs trust, refunds and rankings.
- Ask for original material: real numbers, customer stories, screenshots, photos, prices, years in
  business, credentials. Original data is what makes a page worth ranking over competitors.
- Put a placeholder wherever info is missing, and track it.

## Phase 5: Professional pages (read `references/professional-pages.md`)

Product or company site: Terms, Privacy, Cookies (if any tracking exists), Security, Contact, About,
plus KVKK/GDPR text when relevant. Personal site: About, Contact, social links, and a services or
portfolio page if one fits. For each legal page, ask Yes / Yes with banner / No. For any yes, collect
the legal facts first (entity, country, user locations, data location, processors, cookies,
retention, age limits, data-request contact) and never invent them.

## Phase 6: Implementation (read `references/technical-seo.md`)

Get the final go-ahead (file list), then build:
- **On-page:** a unique title (~50–60 chars) and meta description per page; exactly one H1 stating
  the page topic; a logical H2/H3 hierarchy; descriptive `alt` on content images (`alt=""` on
  decorative ones); lowercase hyphenated URLs; a self-referencing canonical; Open Graph/Twitter
  tags; `lang` on `<html>`. Keywords appear naturally, and readability beats keyword density every
  time.
- **Structured data (JSON-LD), truthful only:** Organization/Person, WebSite,
  SoftwareApplication/Product/Service, LocalBusiness (real address and phone, otherwise
  placeholders), BreadcrumbList, BlogPosting (real author), FAQPage. No made-up ratings.
- **Internal links:** every important page is reachable from every entry page through real
  `<a href>` links (nav, footer, breadcrumbs, body). No orphans, and ≤ 3 clicks from home to every
  important page. Example: `/blog/what-is-a-qr-menu` → `/qr-menu` → `/pricing`.
- **Crawlability:** `robots.txt` served at the site root, allowing important URLs, disallowing only
  private or utility routes, never blocking CSS/JS, with a `Sitemap:` line. `sitemap.xml` with
  absolute canonical `loc`s for indexable pages only and a real per-page `lastmod`.
- **Duplicates:** canonicals, a consistent trailing-slash policy, one URL per piece of content,
  `noindex` on thin utility pages. Report www/non-www and http/https issues to the user, since those
  are server config.
- **Rendering:** navigation uses `<Link href>` / `<a href>`, never `<div onClick={() =>
  router.push(...)}>`, because crawlers follow hrefs, not click handlers. Static content lives in
  server-rendered HTML, not client-side fetches. In Next.js, pages and layouts stay Server
  Components, and `'use client'` goes on the smallest interactive leaf only. For a pure client SPA,
  explain the indexing risk and *propose* prerendering/SSG. Don't migrate without approval.

## Phase 7: Verification (read `references/verification.md`)

- **Raw HTML:** serve a production build (or static files) and run
  `python "SKILL_DIR/scripts/crawl_check.py" <base-url> --sitemap`. It checks status codes, redirect
  chains, titles, meta, H1s, canonicals, alt text, duplicates, orphans, click depth, soft 404s and
  leftover placeholders, all from JS-free HTML. Then run
  `python "SKILL_DIR/scripts/sitemap_check.py" <base-url>`.
- **Status codes:** report problems to the user. Never fix backend or server config. A purely
  frontend fix (a broken `href`) still needs a quick yes.
- **Mobile:** built-in browser screenshots at 360, 390, 768 and 1280 px for every new or changed
  page. Check for horizontal overflow, usable buttons/links, working mobile nav, and content parity
  with desktop.
- **Speed:** `python "SKILL_DIR/scripts/psi.py" <live-url>` (mobile + desktop) against LCP < 2.5 s,
  INP < 200 ms, CLS < 0.1. Not deployed yet → mark as **pending**, do the static checks from the
  reference, and tell the user to re-run verification after deploying.
- **UX checklist:** fast · mobile-friendly · HTTPS · stable layout · readable · no intrusive popups
  · main content visible immediately · usable navigation.

If you can't start a server (no dependencies installed, or the user declined an install), say so,
mark runtime checks as pending, and still run `source_audit.py` on the changed files.

## Phase 8: Report

Update `seo/seo-plan.json` and `seo/seo-plan.md`, then reply with these sections in this order:

1. **Pages**: a table of path · primary keyword · intent · created/changed/unchanged.
2. **Open placeholders**: each one with the file and what you need from the user.
3. **Backend and server issues**: problems the user must fix (status codes, redirects, HTTPS, www).
4. **Search Console steps**: click-by-click (template in `references/verification.md`), plus the
   URLs to request indexing for first.
5. **Pending checks**: e.g. Core Web Vitals after deploy, mobile screenshots if no server ran.
6. **SEO feature suggestions**: ideas that would help ranking, such as indexable public pages per
   customer, a comparison page, review collection, a Google Business Profile, or more blog topics
   from the People Also Ask research. These are suggestions only and nothing is built without
   approval.

## When the user comes back

A later run with new words starts at Phase 0. The state file tells you which keywords each page
already owns. New words either join an existing page as secondary keywords or get a new page. Never
create a second page competing for an owned keyword.
