# <TICKER>.md layout

Copy this skeleton exactly; replace `‹…›`. English only (the JSON sidecar carries TR).
Keep section numbers. Tables over prose — see `rules.md` §2.

````markdown
# ‹Name› (‹EXCHANGE›:‹TICKER›)

| Price | 1D | Mkt cap | EV | Sector | Currency | Data timestamp |
|---|---|---|---|---|---|---|
| ‹292.00› | ‹+1.9%› | ‹403.0B› | ‹1.02T› | ‹Transportation› | ‹TRY› | ‹2026-10-03 17:05 UTC› |

| Short (≤3 mo) | Medium (6–12 mo) | Long (1–3 yr) | Manipulation | CEO trust | News risk | Bank view | Class |
|---|---|---|---|---|---|---|---|
| **‹6.1›/10** | **‹6.3›/10** | **‹6.6›/10** | ‹M› | ‹M› | ‹M› | ‹3B·1H·0S› | ‹Transitional› |

## 1. What the company does
### 1a. Today
‹≤ 60-word summary›

| Segment | Revenue | % total | YoY | Op. margin | Key products | Src |
|---|---|---|---|---|---|---|

```mermaid
pie title Revenue mix FY‹2025›
  "‹Segment A›" : ‹60›
  "‹Segment B›" : ‹40›
```

| Region | Revenue | % total |
|---|---|---|

| Role | Company | Provides / buys | Dependency | Substitutable | Src |
|---|---|---|---|---|---|

### 1b. Future plans
‹≤ 60-word summary›

| Initiative | Target market | Timeline | Investment | Status | Competitive goal (vs whom) | Src |
|---|---|---|---|---|---|---|

### 1c. Future-proofing — `‹Innovative|Transitional|Traditional›`
‹≤ 60-word summary›

| R&D % rev | Peer median | Rev from < 3y products | IP position | Disruption exposure | Moat (yrs) |
|---|---|---|---|---|---|

## 2. Competition
### 2a. Market size & share
| Segment | TAM | TAM CAGR | Our share | Trend (3y) | #1 player | Src |
|---|---|---|---|---|---|---|

One pie per segment:
```mermaid
pie title ‹Segment› share (TAM ‹$X›)
  "‹Us›" : ‹20›
  "‹Rival 1›" : ‹15›
  "Others" : ‹65›
```

### 2b. Size & differentiators
| Company | Mkt cap $ | Revenue $ | Growth | Gross m. | Op. m. | Net m. | R&D % | FCF $ | P/E | EV/EBITDA |
|---|---|---|---|---|---|---|---|---|---|---|
| **‹Us›** | | | | | | | | | | |
| Peer median | | | | | | | | | | |

| Capability | ‹Us› | ‹Peer 1› | ‹Peer 2› |
|---|---|---|---|
| ‹…› | ✓ lead | ~ par | ✗ behind |

| Better at (metric) | Worse at (metric) |
|---|---|

### 2c. SWOT (≥ 5 items each)
| S — Item | Evidence / metric | Impact | Horizon | Src |
|---|---|---|---|---|

(same for W; O and T add a `Prob.` column)

## 3. Financials (‹currency›; FY + TTM)
| FY | Revenue | YoY | Gross profit | Op. income | Net income | YoY | EPS | FCF | GM | OM | NM |
|---|---|---|---|---|---|---|---|---|---|---|---|

```mermaid
xychart-beta
  title "Revenue vs net income (‹B TRY›)"
  x-axis [2021, 2022, 2023, 2024, 2025]
  y-axis "‹B TRY›"
  bar [‹…›]
  bar [‹…›]
```
```mermaid
xychart-beta
  title "YoY growth % — revenue vs net income"
  x-axis [2022, 2023, 2024, 2025]
  y-axis "%"
  line [‹…›]
  line [‹…›]
```

| Metric | 5y CAGR | 3y CAGR | Last YoY | Peer median |
|---|---|---|---|---|

| FY | Metric | Change | Cause (≤ 12 words) | 1-off / recurring | Impact | Duration | Src |
|---|---|---|---|---|---|---|---|

| Cash | Total debt | Net debt/EBITDA | Current ratio | Interest coverage | Equity ratio |
|---|---|---|---|---|---|

## 4. Price & risk
### 4a. Valuation
| Multiple | Current | 5y avg | Peer median | Prem./disc. | Verdict |
|---|---|---|---|---|---|

| Mkt cap | EV | Fair low | Fair mid | Fair high | Upside |
|---|---|---|---|---|---|

| Method | Value/share | Assumptions |
|---|---|---|

| Target low | mean | high | Buy | Hold | Sell |
|---|---|---|---|---|---|

### 4b. 1-month expectation — expected move **‹+1.0%›**
| Scenario | Move | Target | Prob. | Main driver (≤ 8 words) |
|---|---|---|---|---|
| Bear | | | | |
| Base | | | | |
| Bull | | | | |

| RSI 14 | vs SMA50 | vs SMA200 | 30d vol (ann.) | Next earnings |
|---|---|---|---|---|

| Date | Catalyst (next 30 days) |
|---|---|

### 4c. Manipulation susceptibility — **‹Low›** (‹4› pts)
| Input | Value | Points |
|---|---|---|

### 4d. CEO trust — ‹Name› (since ‹YYYY›) · ‹6.5›/10 · ‹M›
| Criterion | Value | Points | Src |
|---|---|---|---|

### 4e. World-news exposure
| Theme | Channel | Dir. | Risk | Horizon | Conf. |
|---|---|---|---|---|---|

### 4f. Stock news (tier-1, 30 days)
| Date | Outlet | Headline | Dir. | Impact | Horizon | Priced in |
|---|---|---|---|---|---|---|

## 5. Bank research (180 days)
| Bank | Role | Rating (orig → B/H/S) | Target | Upside | Date | Action | Important topics | Niche topics | Src |
|---|---|---|---|---|---|---|---|---|---|
| JPMorgan | fixed | ‹Overweight› → **‹Buy›** | ‹320 USD› | ‹+36.8%› | ‹2026-08-27› | ‹▲ PT 280→320› | ‹…; …› | ‹…› | ‹s12› |
| Bank of America | fixed | ‹…› |
| Morgan Stanley | fixed | ‹…› |
| Goldman Sachs | fixed | No coverage (180d) | – | – | – | – | – | – | – |
| ‹Citi› | substitute | ‹…› |
| ‹İş Yatırım› | local | ‹AL → Buy› | ‹455 TRY› | … | ← BIST only |

- Uncovered fixed bank: keep the row, write `No coverage (180d)`.
- ADR target: `2,400 USD (US listing ASML; ≈ 2,133 EUR)`; upside vs the ADR price.
- Covered but no public coverage of the note: topics `Not reported publicly`.
- Rating change in window: Action `Hold → Buy (2026-07-31)`.

| Bank view | Buy | Hold | Sell | Big-4 covering | Median target | Median upside | Raises / cuts (180d) |
|---|---|---|---|---|---|---|---|

```mermaid
xychart-beta
  title "Price-target history (‹USD›)"
  x-axis ["‹2026-05-21›", "‹2026-08-27›"]
  y-axis "‹USD›"
  line [‹280, 320›]
  line [‹288, 300›]
```
(one line per bank with ≥ 2 points; omit the chart if no bank has 2 points)

## 6. Score
‹paste the table printed by scripts/scores.py›

## Sources
1. ‹title› — ‹url› (‹date›)

_Not investment advice. Data as of ‹timestamp›._
````
