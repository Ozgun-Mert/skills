# Analysis & writing rules

Every stock subagent obeys these. `scripts/validate_report.py` enforces the checkable ones.

## 1. Data integrity
1. **No number from memory.** Every figure comes from a script output in `data/<TICKER>/` or a cited tier-1 / official source (10-K, 20-F, annual report, KAP disclosure, investor presentation). Your training data is stale — prices, CEOs, even fiscal-year results change. Example: on 2026-10-03 Apple's CEO per Yahoo was John Ternus, not Tim Cook.
2. **Source priority:** official filing > TradingView > Yahoo. Scripts already apply it; if you override a script value with a filing value, cite the filing.
3. **Every table** has a `Source` column or a footer line `Source: … · data <date>`. In the JSON sidecar use `source: "s<N>"` pointing into `sources[]`.
4. **Missing = `N/A` + reason.** Never fill gaps with estimates. Estimates are allowed only in forecast / fair-value fields and are labeled `est.`.
5. **Discrepancies** listed in `financials.json` / `price.json` must be shown as a note under the affected table.
6. **Currency:** detail tables use the reporting currency (`financials.json.currency`). Comparisons across stocks use USD (`*_usd` fields; FX rate + source in a footnote).
7. **Basis notes:** if `financials.json` has `basis_note` (IAS 29 restatement / mixed basis), print it under the financials table and use one basis for growth judgments.
8. **Hyperinflation guard (TRY, ARS, NGN, EGP…):** nominal growth is mostly inflation. Show `revenue_usd` / `net_income_usd` growth next to nominal and base growth judgments on USD figures.

## 2. Writing style (strict)
1. Tables, charts, scores and tags first. Write a sentence only when nothing else can carry it.
2. **Exception — Section 1:** each of 1a/1b/1c gets one prose summary of **≤ 60 words**.
3. Outside Section 1: notes **≤ 12 words** (`cause`, `driver`, `note`, `duration`, `channel`). No paragraphs, no intros/outros, no "In conclusion", no "It is worth noting".
4. Use tags instead of words: `▲/▼/■`, `L/M/H`, `✓/✗`, `+/−`, `1-off / recurring`, `lead / par / behind`.
5. Markdown charts use Mermaid `pie` and `xychart-beta`. One measure per chart — never put % growth and absolute values on two y-axes; make two charts.
6. Numbers: compact units (`416.2B`, `12.4%`), sign on changes (`+6.4%`), one decimal for ratios.
7. Every short text in the JSON sidecar is `{ "en": "...", "tr": "..." }` — real Turkish, not a copy of the English.

## 3. Analytical depth
1. **No generic or obvious statements.** Banned (and anything like them): "strong brand", "better advertising", "duopoly" (e.g. Pepsi/Coca-Cola), "competition is high", "depends on the economy", "good management", "market leader", "innovative products", "supply chain risk", "macro uncertainty".
2. Each SWOT / risk item is **specific, quantified where possible, and second-order** — it names the mechanism, the counterparty, the number and the time window.
   - ✗ "Supply chain risk"
   - ✓ "TSMC N2 capacity ~X% pre-booked by AAPL → NVDA Rubin ramp constrained until 2027"
   - ✗ "Strong brand"
   - ✓ "Services gross margin 75% vs hardware 36% → mix shift adds ~40bp/yr to group GM"
3. **Peers per business segment**, not per sector. GOOGL: Ads → META, AMZN · Cloud → AMZN, MSFT · Waymo → TSLA, Zoox (AMZN), Baidu Apollo. One market-share pie per segment.
4. **Anomalies:** any YoY move in revenue / op income / net income / FCF that deviates > 15 pp from the 5y trend gets an anomaly row: cause, 1-off vs recurring, impact size, impact duration (e.g. "2 quarters", "until FY27"). Example: layoff severance → 1-off, margin recovers next FY.
5. **1-month forecast** is anchored on data: RSI, distance to SMA50/200, 30d realized vol, catalysts dated within 30 days (earnings date from `price.json.quote.next_earnings_date`), news flow. A base case outside ±1.5× the 30d monthly vol (`vol_30d_ann / √12`) needs a dated catalyst.
6. **News:** only Bloomberg, Reuters, FT, WSJ, CNBC (equal weight) plus official disclosures (SEC 8-K, KAP, company IR). Other outlets may lead you to a fact but are never cited.

## 4. Data freshness
- Run the scripts in **this** session; never reuse `data/` from an earlier day.
- Price < 1 trading day old; financials = latest filed FY + TTM; news = last 30 days (`--days 60` if < 3 items).
