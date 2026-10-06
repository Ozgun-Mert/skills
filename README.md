# skills

Claude Code skills. Each folder is one skill; the repo is the source of truth and an install
script copies it into `~/.claude/skills/` so the slash command works in every project.

| Skill | Command | What it does |
|---|---|---|
| [stock-analyzer](stock-analyzer/) | `/analyze-stock` | Data-driven, multi-agent stock analysis with a shareable dashboard |
| [seo-optimizer](seo-optimizer/) | `/optimize-seo` | People-first SEO: keyword research, intent → page map, pages and technical SEO, with approval at every step |
| [backend-checker](backend-checker/) | `/check-backend-security` · `/check-backend-code-quality` · `/check-backend-health` | Backend security audit and code-quality review as gitignored reports in `docs/`, incremental and token-efficient |

---

## stock-analyzer — `/analyze-stock`

```
/analyze-stock aapl
/analyze-stock aapl, nvidia, amd, THYAO, BIST:ASELS
```

Accepts tickers or company names, comma-separated. Supports US, BIST (Turkey) and global
equities. ETFs, funds and crypto are rejected. Ambiguous names (e.g. `TM`) trigger a question.

### Output

Written to `./stock-reports/<YYYY-MM-DD>/` in the directory where the command runs:

| File | Content |
|---|---|
| `<TICKER>.md` | Table-first report (English); prose only in Section 1 |
| `<TICKER>.json` | Machine-readable mirror with EN/TR labels, validated against a schema |
| `world-context.md/.json` | Current world-news themes with severity and affected sectors |
| `data/<TICKER>/*.json` | Raw script outputs with source URLs and fetch timestamps |
| `dashboard.html` | Published as one shareable artifact |

The dashboard opens on the stock's detail view for a single ticker. For several tickers it opens
on a comparison page: KPI strip, a filterable and sortable table (incl. bank view), score, valuation,
growth, margin and bank-upside charts, a risk map and component heatmap. Clicking a stock opens its full detail. Both
views have an EN/TR toggle and light/dark themes.

### What each report covers

| Section | Contents |
|---|---|
| 1 · Business | Revenue by segment and geography, value chain with dependency levels, roadmap, future-proof class (Innovative / Transitional / Traditional) |
| 2 · Competition | TAM and market-share pie per segment, peer table in USD, differentiator matrix, SWOT with ≥ 5 specific, quantified items per quadrant |
| 3 · Financials | 5 fiscal years + TTM, YoY and CAGR, anomalies (cause, 1-off vs recurring, impact duration), balance-sheet health |
| 4 · Price & risk | Multiples vs 5y average and peers, fair value, 1-month bear/base/bull with probabilities, manipulation index, CEO trust, world-news and stock-news exposure |
| 5 · Bank research | JPMorgan, Bank of America, Morgan Stanley, Goldman Sachs (always shown) + up to 3 substitutes (Citi, UBS, Barclays, Deutsche Bank, Wells Fargo, HSBC) and, for BIST, up to 3 local brokers: Buy/Hold/Sell, price target, upside, date, action, important and niche topics from each note (last 180 days) |
| Score | Short (≤ 3 mo), medium (6–12 mo) and long (1–3 yr) scores out of 10, from a fixed weighted rubric (C1–C5) |

### How a run works

1. Resolve inputs to listings (`resolve_ticker.py`).
2. One subagent maps current world news (tier-1 outlets only).
3. One subagent per stock, in parallel: fetches data, researches, scores with `scores.py`,
   writes the md + JSON, and must pass `validate_report.py`.
4. The main agent builds `dashboard.html` and publishes it as an artifact.

### Data sources

| Data | Primary | Fallback |
|---|---|---|
| Price, volume, technicals, multiples, analyst targets | TradingView scanner | Yahoo Finance |
| Financial statements | SEC EDGAR XBRL (US) · TradingView (others) | Yahoo Finance |
| News | Bloomberg, Reuters, FT, WSJ, CNBC (via Google News RSS, headline-filtered) | — |
| Official disclosures | SEC 8-K/10-Q (US) · KAP (BIST) | — |
| Ownership, short interest, insiders, CEO | Yahoo Finance | — |
| Bank ratings & price targets | Yahoo upgrades/downgrades (primary listing, else US ADR) · İş Yatırım company card (BIST) | cited press article |
| Bank report topics | Coverage of each note: tier-1 + Barron's, MarketWatch, Investing.com, TipRanks, TheFly, StreetInsider (+ Bloomberg HT for BIST) | — |

Agents may not use numbers from memory. Missing data is shown as `N/A` with a reason, and
disagreements between sources are listed as discrepancies.

### Install

Requires Python 3.10+ (tested on 3.14) and Windows PowerShell.

```bash
powershell -ExecutionPolicy Bypass -File stock-analyzer/install.ps1
```

This copies the skill to `%USERPROFILE%\.claude\skills\analyze-stock\` and installs
`requirements.txt`. Re-run it after editing anything in `stock-analyzer/`. Start a new
Claude Code session to pick up the command.

### Running the scripts directly

```bash
python stock-analyzer/scripts/resolve_ticker.py "nvidia, THYAO"
```

```bash
python stock-analyzer/scripts/run_all.py --input nvidia --outdir out/NVDA
```

```bash
python stock-analyzer/scripts/fetch_bank_research.py --tv EURONEXT:ASML --yahoo ASML.AS --name "ASML Holding NV" --adr ASML
```

```bash
python stock-analyzer/scripts/validate_report.py stock-reports/2026-10-03/NVDA.json
```

```bash
python stock-analyzer/scripts/build_dashboard.py --dir stock-reports/2026-10-03
```

To test the dashboard without a full analysis, build placeholder sidecars from real fetched
numbers (qualitative fields are marked `[fixture]`; never publish these):

```bash
python stock-analyzer/tests/make_fixture.py --data out --out out/report
```

### Layout

```
stock-analyzer/
├── SKILL.md              # the skill (name: analyze-stock)
├── stock-analyzer.md     # copy of SKILL.md, kept in sync by install.ps1
├── install.ps1
├── requirements.txt
├── scripts/              # data fetchers, scorer, validator, dashboard builder
├── references/           # rules, scoring rubric, index definitions, report template,
│                         # JSON schema, subagent briefs
├── templates/dashboard.html
└── tests/make_fixture.py
```

### Score weights

| Component | Short (≤ 3 mo) | Medium (6–12 mo) | Long (1–3 yr) |
|---|---|---|---|
| C1 Business | 5% | 15% | 30% |
| C2 Competition | 10% | 15% | 20% |
| C3 Financials | 10% | 20% | 25% |
| C4a Valuation | 20% | 20% | 10% |
| C4b Momentum & risk | 45% | 15% | 5% |
| C5 Bank consensus | 10% | 15% | 10% |

### Known limitations

- TradingView's scanner is an unofficial endpoint. If it changes, scripts fall back to Yahoo.
- Bloomberg has no free API, so coverage comes from headlines found through Google News.
- Short interest is usually unavailable outside the US (scored as 1 point and labeled).
- Bank reports are client-only. Ratings/targets are structured data; report topics come only from press
  coverage of each note, so a covered bank can show "Not reported publicly". Yahoo's grade feed has gaps
  (flagged for the agent to verify from the press).
- Turkish companies report under IAS 29 hyperinflation accounting. Sources disagree on
  restated vs nominal figures; the scripts align them and add a `basis_note`.

_Not investment advice._

---

## seo-optimizer — `/optimize-seo`

```
/optimize-seo ['qr menü', 'karekod menü']
/optimize-seo
```

Run it inside a website project (or an empty folder). Words are optional and can be written as a
list, comma-separated or quoted (`qr menü, karekod menü` works too). `/optimize-SEO` also works.

| Input | What happens first |
|---|---|
| Words given | Reads the project, expands the words with close variants (synonyms, spellings, long-tail, local forms), asks you to approve the list |
| No words, existing site | Reads the frontend and proposes a prioritized word list, each with a reason |
| No words, empty folder | Interviews you (product, audience, market, language, competitors, pages), then proposes words and a stack (Next.js by default, never scaffolded without a yes) |

The goal is for **the website** to rank, not for the landing page to match every phrase. Each
search intent gets the page that answers it best (blog post, keyword page, pricing, about,
contact), and the landing page stays short. A search like "nişantaşı arabuluculuk" can be won by
the Contact page.

### How a run works

| Phase | What | Your approval |
|---|---|---|
| 0 Preflight | Reads `seo/seo-plan.json` from earlier runs, adds `/seo/` to `.gitignore`, audits the source (`source_audit.py`), maps the backend paths it must never touch, asks for the live URL | — |
| 1 Words | Mode chosen from the table above; asks about language, country, city | Word list |
| 2 Research | Top-3 Google results per word (built-in browser; WebSearch fallback if Google shows a CAPTCHA), People Also Ask, relevance verdict per result → `seo/research/` | — |
| 3 Keyword map | Sub-keywords × intent (informational, commercial, pricing, local, brand) → one page per primary keyword, no duplicates or doorway pages | One table, one row per page: yes / no / yes but change |
| 4 Briefs | Outline per page, gap vs. competitors, product claims to confirm, original data to supply | Claims list |
| 5 Trust pages | About, Contact, Terms, Privacy, Security, KVKK/GDPR… | Yes / Yes with banner / No per legal page |
| 6 Build | Titles, meta, H1–H3, alt text, clean URLs, canonicals, JSON-LD, internal links, robots.txt, sitemap.xml, server-rendered links and content | File list go-ahead |
| 7 Verify | Raw-HTML crawl (`crawl_check.py`), robots/sitemap (`sitemap_check.py`), status codes, mobile screenshots at 360/390/768/1280 px, Core Web Vitals via PageSpeed (`psi.py`, deployed URL) | Fixes to pre-existing code |
| 8 Report | Pages, open placeholders, backend/server issues for you, Search Console steps, pending checks, SEO feature ideas | — |

### What you get

| Where | Content |
|---|---|
| The project itself | New and updated frontend pages and components, `robots.txt`/`app/robots.ts`, `sitemap.xml`/`app/sitemap.ts`, JSON-LD, metadata. Nothing is committed: review the diff yourself |
| `seo/seo-plan.json` + `.md` | Word list, keyword → page map, rejected rows, confirmed/denied features, open placeholders, issues for you, pending checks, suggestions. Gitignored; later runs read it so they don't repeat questions or create competing pages |
| `seo/research/<keyword>.md` | Top-3 results per keyword: outlines, what they miss, relevance verdicts, source links |
| `seo/crawl.json`, `seo/sitemap-check.json`, `seo/psi-*.json` | Raw verification results |
| Final reply | The six report sections above, in the language you use |

Missing facts (prices, phone, address, author, legal details) are never guessed. They appear on
the page as `{{PLACEHOLDER: name}}` so they can't ship unnoticed. Find them all with:

```bash
grep -rn "{{PLACEHOLDER:" .
```

### What it asks you for

- Answers at each approval step (it stops and waits; it never continues on a guess).
- The production URL, if the site is live: needed for canonicals, the sitemap, status checks and PageSpeed.
- An optional, free [PageSpeed Insights API key](https://developers.google.com/speed/docs/insights/v5/get-started).
  The keyless quota is shared worldwide and is often used up. Pass it with `--key` or the
  `PSI_API_KEY` env var; it is never written to files.
- API contracts (endpoint, request/response shape, auth) if a page needs backend data.

### Rules it follows

- Never edits backend code (API routes, server, DB/ORM, auth, `.env*`). Asks before touching
  ambiguous config (`middleware.ts`, `next.config.*`, `vercel.json`).
- Never fabricates stats, reviews, testimonials, ratings, features or legal facts.
- Never copies competitor text; never solves CAPTCHAs.
- Never runs git commands that change anything (only adds `/seo/` to `.gitignore`).
- Leaves visuals alone unless they hurt SEO, and then asks.
- Legal pages marked "Yes with banner" get a visible notice that the text is AI-generated and
  must be reviewed by a lawyer.

### Install

Requires Python 3.10+ (standard library only, nothing to pip install) and Windows PowerShell.

```bash
powershell -ExecutionPolicy Bypass -File seo-optimizer/install.ps1
```

Copies the skill to `%USERPROFILE%\.claude\skills\optimize-seo\`. Re-run it after editing anything
in `seo-optimizer/`. Start a new Claude Code session to pick up the command.

### Running the scripts directly

| Script | What it does |
|---|---|
| `ensure_gitignore.py` | Adds `/seo/` to `.gitignore` once, detects a clashing `seo/` app folder, verifies with `git check-ignore`, reports already-tracked state files |
| `source_audit.py` | Static audit, no build needed: stack, routes, metadata, robots/sitemap, JSON-LD, page-level `'use client'`, `onClick` navigation, missing `alt`, H1 counts, client-side fetching, placeholders, backend paths |
| `crawl_check.py` | Crawls a served site without JavaScript or auto-redirects: status codes, redirect chains, title/description/H1/canonical/lang, duplicates, orphans, click depth, soft 404s, leftover placeholders |
| `sitemap_check.py` | Validates robots.txt and sitemap.xml: absolute canonical URLs, lastmod, 200 status, noindex conflicts, blocked assets, pages missing from the sitemap |
| `psi.py` | PageSpeed Insights (mobile + desktop) against LCP < 2.5 s, INP < 200 ms, CLS < 0.1; field data when available, lab data otherwise |

```bash
python seo-optimizer/scripts/ensure_gitignore.py --root path/to/site
```

```bash
python seo-optimizer/scripts/source_audit.py --root path/to/site
```

```bash
python seo-optimizer/scripts/crawl_check.py http://localhost:3000 --sitemap --out seo/crawl.json
```

```bash
python seo-optimizer/scripts/sitemap_check.py http://localhost:3000 --crawl seo/crawl.json
```

```bash
python seo-optimizer/scripts/psi.py https://example.com/ --key YOUR_KEY
```

### Test results

Five scenarios, each run with and without the skill, with the user's answers scripted
(`evals/evals.json`): a Next.js QR-menu SaaS with words, a plain-HTML mediator site with no words,
an empty folder, a client-only Vite/React app, and a word that needs a feature the product lacks.

| | With skill | Without skill |
|---|---|---|
| Checks passed | 59/59 (100%) | 41/59 (73%) |
| Average time / tokens per run | 558 s / 151k | 271 s / 87k |

Without the skill, runs edited backend files, wrote "coming soon" text instead of trackable
placeholders, used legal banners that didn't say the text was AI-generated, kept no state, and
didn't gitignore anything. Both versions handled the empty folder and the missing-feature case
well.

### Known limitations

- Google often blocks automated searches. The WebSearch fallback is not Google's ranking and gives
  weaker results for non-English (e.g. Turkish) queries; the report says when it was used.
- Builds, mobile screenshots and runtime crawls need the project's dependencies installed. The
  skill asks before running `npm install`; without it those checks are reported as pending.
- Core Web Vitals need a deployed URL. Before launch they are pending, and only static
  performance risks are reported.
- A client-only SPA (Vite/CRA) stays weak for SEO until it is prerendered or moved to SSG. The skill
  explains the options but never migrates without approval.
- Redirects, HTTPS, www vs. non-www and soft 404s are server or hosting settings. They are reported
  to you, not fixed.
- Generated legal text is a starting point, not legal advice: have a lawyer review it.

### Layout

```
seo-optimizer/
├── SKILL.md              # the skill (name: optimize-seo)
├── seo-optimizer.md      # copy of SKILL.md, kept in sync by install.ps1
├── install.ps1
├── references/           # research, keyword mapping, content, trust/legal pages,
│                         # per-framework technical SEO, verification, state schema
├── scripts/              # ensure_gitignore, source_audit, crawl_check, sitemap_check, psi
└── evals/evals.json      # test scenarios with scripted user answers
```

---

## backend-checker — `/check-backend-security` · `/check-backend-code-quality` · `/check-backend-health`

```
/check-backend-security api web
/check-backend-code-quality api packages/shared
/check-backend-health api web packages/shared
/check-backend-health api --full
```

The first path is the API directory, and everything in it is analyzed. Further paths (frontend,
shared types) are optional context that is read only where a check needs it, e.g. secrets exposed to
the frontend or prices the backend trusts from the client. Any language or framework. The skills
**only report**: they never edit code, install packages or touch git.

| Command | Runs | Writes |
|---|---|---|
| `/check-backend-security` | Security agent | `docs/SECURITY_PROBLEMS.md` |
| `/check-backend-code-quality` | Code-quality agent | `docs/CODE_QUALITY.md` |
| `/check-backend-health` | Every check in `core/registry.json`, in parallel | all reports |

### What the reports cover

**Security** (severity Critical/High/Medium/Low, OWASP tag, `file:line`, simple fix):

| Section | Topic |
|---|---|
| 1a, 1b | Vulnerable/EOL runtime and libraries with the closest safe version (live OSV.dev + endoflife.date); secrets in git (incl. history) or exposed to the frontend |
| 2a–2c | SQL/NoSQL injection; illogical data operations (FKs, cascades, missing transactions); unnecessary DB work (N+1, over-fetching) |
| 3 | Runs the existing test suite: failing tests with one-sentence reasons, or "Test suite should be implemented" |
| 4a, 4b | Questionable business rules (you're asked whether each is intended; answers are remembered); crash/corruption logic (math, nulls, stale cache) |
| 5a, 5b | IDOR and mass assignment; trusting frontend values (prices, totals, roles) |
| 6a–6c | Unprotected sensitive data at rest; responses returning too much; weak crypto |
| 7–13 | Uploads, CORS (HTTP + WebSocket), security headers, rate limiting (API + per user), idempotency, enumeration messages, helmet or equivalent |
| 14–21 | Auth & sessions (JWT, cookies, reset tokens), input validation & limits, other injection (command, path traversal, SSRF, prototype pollution, ReDoS), CSRF, error leakage & misconfiguration, secrets in logs, payment webhooks, WebSocket auth |

**Code quality** (impact + effort, plans only, no code): repetitive code, typed input contracts,
extensibility (e.g. adding a payment method), long functions/files and nesting, dead code, magic
values, error-handling consistency, response/naming consistency, hardcoded dependencies, and weak or
duplicated types. It ends with a refactor roadmap ordered by impact ÷ effort.

Reports are overwritten on every run. **A fixed problem disappears completely** from the report;
there is no "fixed since last run" section.

### How a run works

| Phase | What |
|---|---|
| 0 Preflight (scripts, no LLM) | `.gitignore` lines; `index.py` builds a map of files, hashes, import graph, stack, runtime, every dependency version, hotspot lines per topic, secrets scan, and test command; `plan.py` decides what each check must analyze |
| 1 Prep (scripts) | `osv_check.py` (vulnerabilities and EOL, cached 7 days), `dupes.py` (duplicate blocks), `quality_scan.py` (long functions, magic values, dead code, weak types) |
| 2 Agents | One check: one subagent. Health: the orchestrator reads the bundled code **once**, then forks one agent per check in one message, so they share it through the prompt cache (falls back to parallel subagents) |
| 3 Merge | `findings.py` merges agent JSON with earlier findings: re-analyzed files are replaced, unchanged ones carried over, fixed ones vanish; 4a questions are asked once and remembered |
| 4 Render | `findings.py render` writes the markdown with a summary table; the reply lists counts and what to fix first |

**Incremental by default.** On a re-run only changed files, the files importing them, and
cross-cutting sections whose inputs changed (CORS config, manifests, auth middleware…) are
re-analyzed. With no changes no agent runs at all. `--full` forces a complete scan.

### Privacy

`docs/SECURITY_PROBLEMS.md`, `docs/CODE_QUALITY.md` and `docs/.backend-checks/` are added to
`.gitignore`, because the security report is a map of your weaknesses. Secret values are masked
(first 4 characters only). Only package names and versions are sent to external services (OSV,
endoflife.date, npm/PyPI registries); source code never leaves the machine.

### Install

Requires Python 3.10+ (standard library only) and Windows PowerShell.

```bash
powershell -ExecutionPolicy Bypass -File backend-checker/install.ps1
```

Installs every skill under `backend-checker/skills/` to `%USERPROFILE%\.claude\skills\<name>\`, each
with a copy of `core/`. Re-run it after editing anything in `backend-checker/`. Start a new Claude
Code session to pick up the commands.

### How to add a check

1. Write `core/agents/<id>.md`: the checklist the agent follows on top of `agent-contract.md`.
2. Write `core/references/sections-<id>.json` with the report sections and severity/impact scale.
3. Add an entry to `core/registry.json`: id, title, brief, sections file, output report, hotspot
   keys, prep scripts, and cross-cutting sections.
4. Add `skills/check-backend-<id>/SKILL.md`, copying one of the existing thin ones and changing
   `CHECKS`.
5. Re-run `install.ps1`. `/check-backend-health` picks the new check up from the registry with no
   changes, and `ensure_gitignore.py` ignores its report automatically.

### Running the scripts directly

```bash
python backend-checker/core/scripts/index.py --root . --api api --extra web
```

```bash
python backend-checker/core/scripts/plan.py --root . --checks all
```

```bash
python backend-checker/core/scripts/osv_check.py --root .
```

```bash
python backend-checker/core/scripts/findings.py render --root . --check security
```

### Layout

```
backend-checker/
├── install.ps1
├── skills/                    # thin entry points, one per slash command
│   ├── check-backend-security/SKILL.md
│   ├── check-backend-code-quality/SKILL.md
│   └── check-backend-health/SKILL.md
├── core/                      # copied into every installed skill
│   ├── registry.json          # every check; health runs them all
│   ├── agents/                # agent-contract.md + one brief per check
│   ├── references/            # pipeline.md (orchestrator), sections-*.json, framework-equivalents.md
│   └── scripts/               # index, plan, bundle, osv_check, dupes, quality_scan, run_tests,
│                              # findings (merge/questions/decide/render), ensure_gitignore
└── evals/evals.json           # scenarios on seeded Express and FastAPI fixtures
```
