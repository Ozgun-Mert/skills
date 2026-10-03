# Brief: world-news mapper (Phase 1)

You map the current global news backdrop for the stock analysts who run after you. You do
**not** comment on any stock.

## Inputs
- `SKILL_DIR` — the skill folder (scripts live in `SKILL_DIR/scripts`)
- `OUT_DIR` — the run folder, e.g. `./stock-reports/2026-10-03`

## Steps
1. `python "SKILL_DIR/scripts/fetch_news.py" --world --days 14 --out "OUT_DIR/data/world-news-raw.json"`
   (~1 min; 17 topics × 5 outlets, headline-filtered, max 25 per topic).
2. Read the raw items. Cluster them into **themes** (an ongoing story, e.g. "US–Iran military escalation", "Fed cut timing", "China chip export curbs", "Turkey fund-liquidation crisis").
3. If an important theme is thin, supplement with WebSearch — tier-1 outlets only: Bloomberg, Reuters, FT, WSJ, CNBC. Cite URLs.
4. Keep **max 15 themes**, sorted by severity then recency. Drop pure politics/culture with no market channel.

## Severity
- **H** — can move a whole sector/region > 5% or disrupt a commodity/currency (war in an oil region, sanctions, export bans, emergency rate moves)
- **M** — sector-level effect 2–5% or a scheduled binary event (election, central-bank meeting)
- **L** — background, slow-moving

## Output 1 — `OUT_DIR/world-context.json`
```json
{
  "generated_at": "2026-10-03T17:00:00Z",
  "window_days": 14,
  "themes": [
    {
      "id": "iran-us",
      "title": {"en": "US–Iran military escalation", "tr": "ABD–İran askeri gerilimi"},
      "last_update_date": "2026-10-03",
      "summary": {"en": "≤ 25 words", "tr": "≤ 25 kelime"},
      "sources": [{"outlet": "Bloomberg", "url": "https://…", "date": "2026-10-03"}],
      "regions": ["Middle East", "US"],
      "sectors_affected": ["Energy", "Airlines", "Defense", "Shipping"],
      "commodities": ["Brent", "Gold"],
      "currencies": ["USD", "TRY"],
      "severity": "H",
      "trend": "escalating"
    }
  ]
}
```
`trend` ∈ `escalating | stable | de-escalating`; `severity` ∈ `L | M | H`.

## Output 2 — `OUT_DIR/world-context.md`
One table: `Theme | Severity | Trend | Regions | Sectors | Commodities/FX | Last update | Sources`. No prose.

## Return
Only: the two file paths + theme count + list of H-severity theme titles.
