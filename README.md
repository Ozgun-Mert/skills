# skills

Claude Code skills. Each folder is one skill; the repo is the source of truth and an install
script copies it into `~/.claude/skills/` so the slash command works in every project.

| Skill | Command | What it does |
|---|---|---|
| [stock-analyzer](stock-analyzer/) | `/analyze-stock` | Data-driven, multi-agent stock analysis with a shareable dashboard |

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
