---
name: analyze-stock
description: Data-driven multi-agent stock analysis. Use when the user types /analyze-stock, asks to analyze a stock or a list of tickers/company names (e.g. "analyze aapl, nvidia, amd", "should I invest in THYAO", "compare ASML and TSMC"), wants a stock score, SWOT, valuation, 1-month price expectation, or manipulation/news risk for US, BIST (Turkey) or global equities. Fetches live prices and statements via scripts (TradingView, SEC EDGAR, Yahoo), tier-1 news (Bloomberg, Reuters, FT, WSJ, CNBC), writes a table-first .md report per stock and publishes one shareable dashboard artifact with EN/TR toggle.
argument-hint: "<ticker or name>[, <ticker or name>, ...]"
---

# /analyze-stock

Input: `$ARGUMENTS` — one or more names/tickers, comma-separated (`aapl, nvidia, THYAO, BIST:ASELS`).

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded. All scripts are
`python "SKILL_DIR/scripts/<name>.py"`. Read `SKILL_DIR/references/rules.md` before anything else.

**Hard rules:** never use numbers from memory · every number traces to a script output or a cited
tier-1/official source · outputs are tables/charts/tags; prose only in Section 1 (≤ 60 words each) ·
not investment advice.

Install / update (from the repo): `powershell -ExecutionPolicy Bypass -File stock-analyzer/install.ps1`
(plain `-File` is blocked by the default Windows execution policy).

## Phase 0 — resolve & prepare (main agent)
1. `pip` check once per machine: `python -m pip install -q -r "SKILL_DIR/requirements.txt"`
2. `OUT_DIR = ./stock-reports/<YYYY-MM-DD>` relative to the current working directory; if it exists, use `<YYYY-MM-DD>-<HHMM>`. Create `OUT_DIR/data/`.
3. `python "SKILL_DIR/scripts/resolve_ticker.py" "$ARGUMENTS" --out "OUT_DIR/resolved.json"`
   - `supported: false` (ETF, fund, crypto, not found) → tell the user "‹input›: not supported (‹reason›)" and drop it.
   - `ambiguous: true` → ask the user once (AskUserQuestion) with `candidates`; prefer the primary listing.

## Phase 1 — world-news map (ONE subagent, runs first and alone)
Spawn one `general-purpose` agent with the full text of `SKILL_DIR/references/world-news-brief.md`
plus `SKILL_DIR` and `OUT_DIR`. Wait for it. Output: `OUT_DIR/world-context.json` + `.md`.

## Phase 2 — one subagent PER STOCK (parallel)
Spawn one `general-purpose` agent per resolved stock **in the same message** (batches of max 6).
Prompt = full text of `SKILL_DIR/references/stock-agent-brief.md` + `SKILL_DIR`, `OUT_DIR`, `TODAY`,
and that stock's resolved JSON object. Each writes `OUT_DIR/<TICKER>.md` + `OUT_DIR/<TICKER>.json`
and returns one summary line. Subagents never publish artifacts.

## Phase 3 — validate, build, publish (main agent)
1. `python "SKILL_DIR/scripts/validate_report.py" OUT_DIR/<T1>.json OUT_DIR/<T2>.json …`
   An ERROR → send the errors back to that stock's subagent (SendMessage) once; if it still fails,
   leave it — the dashboard lists it as "data unavailable" instead of dropping it.
2. `python "SKILL_DIR/scripts/build_dashboard.py" --dir "OUT_DIR" --tickers "<T1>,<T2>,…"`
   → `OUT_DIR/dashboard.html` (single stock → opens on its detail view; several → comparison page with a
   filterable/sortable table, comparison charts, click a row for that stock's full detail; EN/TR toggle).
3. Publish `OUT_DIR/dashboard.html` with the Artifact tool (icon `chart`, description
   "Stock analysis for ‹tickers› as of ‹date›"). The template is final — do not restyle it.
   A same-day re-run republishes the same file path to keep the URL.

## Final reply (nothing else)
| Ticker | Price | Short | Medium | Long | Manipulation | Report |
|---|---|---|---|---|---|---|
| ‹T› | ‹292.00 TRY› | ‹6.1› | ‹6.3› | ‹6.6› | ‹M› | [‹T›.md](‹path›) |

+ the artifact link + "Not investment advice."

## Scripts (all print JSON with `fetched_at`, `source`, `errors[]`; never fabricate)
| Script | What |
|---|---|
| `resolve_ticker.py "a, b"` | name/ticker → `tv_symbol`, `yahoo_symbol`, exchange, currency, CIK, ambiguity |
| `run_all.py --tv --yahoo --name [--cik --aliases] --outdir` | runs the 5 fetchers below (≈ 10 s) + `run_summary.json` |
| `fetch_price.py` | TradingView price/perf/volume/float/RSI/SMA; Yahoo 1Y series, realized vol, cross-check |
| `fetch_financials.py` | 5 FY + TTM: EDGAR (US) > TradingView > Yahoo; FX-translated, USD growth, discrepancies |
| `fetch_multiples.py --fin` | current multiples, analyst targets/ratings, 5y P/E · EV/EBITDA · P/S history |
| `fetch_peers.py --subject --peers [--segments]` | peer table in USD + peer medians |
| `fetch_news.py` | stock mode (tier-1 + SEC 8-K / KAP) or `--world` mode |
| `fetch_risk_inputs.py` | ownership, short interest, insiders, CEO, ISS governance, regulatory headlines, manipulation pre-score |
| `scores.py --subs` | the only allowed score calculator |
| `validate_report.py` | schema + semantic checks (scores, probabilities, banned phrasing, 5 FY…) |
| `build_dashboard.py --dir [--tickers]` | embeds sidecars into `templates/dashboard.html` |

References: `rules.md` · `scoring.md` · `indices.md` · `report-template.md` · `report-schema.json` ·
`world-news-brief.md` · `stock-agent-brief.md`.

## Gotchas (verified 2026-10-03)
- TradingView's `global` scanner silently converts market cap / EV / TTM / price targets to **USD** while `close` and `*_fy_h` history stay native. `common.tv_scan` always sends `price_conversion.to_symbol=true`; keep it.
- Yahoo may report statements in the functional currency (THYAO → USD) while TradingView uses TRY. `fetch_financials.py` translates (flows at FY-average FX, balances at FY-end FX). Never mix rows by hand.
- TRY figures grow ~50–200%/yr from inflation — judge growth on `revenue_usd` / `net_income_usd`.
- BIST IAS 29 (TMS 29): Yahoo shows prior years restated to current purchasing power, TradingView the as-reported nominal values (ASELS FY2022 revenue differs ~90%). `fetch_financials.py` rescales Yahoo-only fields to the row's revenue basis and writes `basis_note`; cite the basis under the table.
- NVDA-style fiscal years (ending Jan): TradingView labels them by start year, EDGAR/Yahoo by end year. The script realigns by matching revenue (`tv_fy_label_shift`). EDGAR EPS for old years is pre-split, so EPS comes from TradingView.
- Google News matches article bodies; `fetch_news.py` keeps only headlines naming the company. Thin results → add `--aliases` (press name) or `--days 60`.
- Exact-ticker matches can be cross-listings (`lufthansa` → BET:LUFTHANSA); the resolver prefers the same company's primary listing (XETR:LHA). `google` resolves to NASDAQ:GOOG (class C); pass `NASDAQ:GOOGL` explicitly if wanted.
- Short interest is usually `null` outside the US → score 1 pt and say "not published".
- Invalid TradingView column names return `null`, not an error — check new fields with a live call before relying on them.
