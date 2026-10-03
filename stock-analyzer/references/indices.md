# Index definitions

## Manipulation susceptibility index (Low / Medium / High)

`fetch_risk_inputs.py` pre-scores every input it can (`risk.json.manipulation_index`). The agent
finalizes the missing ones and copies all 7 rows into the report.

| Input | 0 pts | 1 pt | 2 pts | 3 pts |
|---|---|---|---|---|
| Market cap (USD) | > 50B | 2–50B | 300M–2B | < 300M |
| Avg daily $ volume, 30d (USD) | > 500M | 50–500M | 5–50M | < 5M |
| Free float % | > 80% | 50–80% | 20–50% | < 20% |
| Short interest % float | < 3% | 3–10% | 10–20% | > 20% |
| Largest holder / insider % | < 10% | 10–30% | 30–50% | > 50% |
| Halts / regulatory actions / pump episodes (3y) | none | — | — | any confirmed |
| 30d vol ÷ 1y vol (or meme/social spike) | < 1.2 | 1.2–1.6 | 1.6–2.2 | > 2.2 |

Total **0–5 Low · 6–11 Medium · ≥ 12 High**.
- Short interest unknown (common outside the US): score **1** and write value `N/A (not published)`.
- Halts/regulatory: check `risk.json.regulatory_headlines_3y`, SEC/SPK/KAP filings. Headlines about probes into *other* companies don't count.

## CEO trust scorecard (score /10 → ≥ 7 High · 4–6.9 Medium · < 4 Low)

7 rows; points per row as shown (max 10). Every row cites a source.

| Criterion | Max | Evidence |
|---|---|---|
| Tenure & track record | 2 | years in role (cite start date), TSR vs index during tenure, execution of stated goals |
| Guidance accuracy | 2 | company's own guidance vs actual, last 8 quarters (beats / misses) |
| Insider transactions 12M | 1.5 | `risk.json.insider_summary_6m` / Form 4 / KAP; planned 10b5-1 sales are neutral, discretionary selling is negative |
| Pay vs performance | 1 | total pay (`risk.json.ceo.total_pay`, proxy) vs TSR; ISS compensationRisk (1 = best, 10 = worst) |
| Controversies / legal / governance | 1.5 | lawsuits, regulator actions, ISS overallRisk, related-party dealings |
| Capital allocation | 1 | M&A outcomes, buybacks at what valuation, dilution |
| Communication consistency | 1 | promises vs delivered (product dates, targets) |

A CEO in role < 1 year: score track record from prior roles and say so in the value cell.

## News risk levels
- **L** — < 2% plausible price impact, or already priced in
- **M** — 2–7%, or uncertain timing
- **H** — > 7% or binary event (sanctions, export ban, litigation verdict, war escalation in a key market)

`tags.news_risk` = highest level among **not-priced-in** negative items in world exposure + stock news.
