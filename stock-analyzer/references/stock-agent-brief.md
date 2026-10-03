# Brief: per-stock analyst (Phase 2)

You analyze ONE stock and write two files. You do not publish artifacts.

## Inputs (from the main agent)
- `SKILL_DIR`, `OUT_DIR`, `TODAY`
- the resolved ticker object from `resolve_ticker.py` (`tv_symbol`, `yahoo_symbol`, `name`, `exchange`, `cik`, `currency`, …)
- `OUT_DIR/world-context.json` (already written by the world-news mapper)

## Read first
`SKILL_DIR/references/rules.md`, `scoring.md`, `indices.md`, `report-template.md`, `report-schema.json`.

## Checklist
1. **Fetch** (≈ 10 s). Add press aliases when the legal name differs from the press name
   (THYAO → "Turkish Airlines", GOOGL → "Google", 005930 → "Samsung Electronics"):
   ```
   python "SKILL_DIR/scripts/run_all.py" --tv ‹tv_symbol› --yahoo ‹yahoo_symbol› --name "‹name›" \
     [--cik ‹cik›] [--aliases "‹press name›"] --outdir "OUT_DIR/data/‹TICKER›"
   ```
   Read every JSON in `OUT_DIR/data/‹TICKER›/` and `run_summary.json`. Re-run a failed script once; then mark the fields `N/A`.
2. **Segments & peers.** From the latest 10-K / 20-F / annual report (WebFetch/WebSearch; cite URL) get segment revenue, geography, and the competitors per segment. Then:
   ```
   python "SKILL_DIR/scripts/fetch_peers.py" --subject ‹tv_symbol› --peers "‹p1, p2, …›" \
     --segments '{"‹Segment›": ["‹p1›","‹p2›"]}' --out "OUT_DIR/data/‹TICKER›/peers.json"
   ```
3. **News.** `news.json` (stock) + `world-context.json` (macro). If `news.json.count < 3`, re-run `fetch_news.py` with `--days 60` and/or better `--aliases`. Supplement with WebSearch restricted to the 5 tier-1 outlets.
4. **Research the 4 sections** exactly as in `report-template.md`, obeying `rules.md` (no generic SWOT, peers per segment, anomalies explained with duration, TAM per segment with source).
5. **Indices.** Finalize the manipulation index from `risk.json.manipulation_index` (fill missing inputs per `indices.md`). Build the 7-row CEO scorecard.
6. **Scores.** Write `OUT_DIR/data/‹TICKER›/subs.json`, run
   `python "SKILL_DIR/scripts/scores.py" --subs "OUT_DIR/data/‹TICKER›/subs.json"` and copy its numbers + table verbatim.
7. **Write** `OUT_DIR/‹TICKER›.md` (English) and `OUT_DIR/‹TICKER›.json` (schema; every short text `{en, tr}`; `price_series` = `price.json.series`; `s3.years` = 5 FY + a `{"fy":"TTM","ttm":true}` row).
8. **Validate** until it prints `OK`:
   `python "SKILL_DIR/scripts/validate_report.py" "OUT_DIR/‹TICKER›.json"` — fix every ERROR and the WARNs about word counts, untranslated text and missing sources.

## Self-check before returning
- [ ] no number without a source; no number from memory
- [ ] no banned/generic SWOT item; ≥ 5 per quadrant, second-order and quantified
- [ ] 5 FY + TTM present (or `years_missing_reason`)
- [ ] scenario probabilities sum to 100; expected move = probability-weighted
- [ ] no prose outside Section 1 beyond ≤ 12-word notes
- [ ] validator prints OK

## Return to the main agent (nothing else)
```
‹TICKER› | md: ‹path› | json: ‹path› | short ‹x.x› medium ‹x.x› long ‹x.x› | manip ‹L/M/H› | failed data: ‹list or none›
```
