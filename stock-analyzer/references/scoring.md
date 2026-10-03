# Scoring rubric

Score every sub-criterion 0–10 (one decimal) against the anchors below, then run
`python scripts/scores.py --subs subs.json` — never compute weights by hand. The validator
rejects sidecars whose scores don't match `scores.py`.

`subs.json` keys (exact):
```json
{"C1": {"revenue_quality": 0, "value_chain": 0, "roadmap": 0, "future_proof": 0},
 "C2": {"market_share": 0, "moat": 0, "swot_balance": 0},
 "C3": {"revenue_growth": 0, "profit_growth_margins": 0, "earnings_quality": 0, "balance_sheet": 0},
 "C4a": {"multiples": 0, "fair_value_upside": 0},
 "C4b": {"expected_move_1m": 0, "news_risk": 0, "manipulation": "L|M|H", "ceo_trust": 0},
 "C5": {"rating_mix": 0, "target_upside": 0, "revision_trend": 0}}
```
C5 starting values: `python scripts/scores.py --banks data/<TICKER>/banks.json` (deterministic from the script
summary). Recompute by the same formulas if you add press-verified bank rows; never adjust by feel.

## Component sub-criteria and anchors

### C1 Business
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| revenue_quality (30%) | 1 product/customer > 50% of revenue, cyclical, one-time sales | 2–3 segments, some recurring | diversified, > 50% recurring/contracted, pricing power shown |
| value_chain (20%) | single-source critical input (H dependency, not substitutable) | some H dependencies with alternatives | no H dependency without substitute |
| roadmap (20%) | vague, unfunded | funded plans, mixed delivery record | funded, dated, history of shipping on time |
| future_proof (30%) | product being substituted, R&D < peers | Transitional; R&D ≈ peers | Innovative; R&D > peers, > 20% revenue from new products |

### C2 Competition
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| market_share (40%) | small and losing share in main segment | #2–3, stable | #1 with rising share in main segment(s) |
| moat (30%) | none; behind on most differentiators | par on most | lead on most; moat > 10 yrs |
| swot_balance (30%) | H-impact threats dominate | balanced | H-impact strengths/opportunities dominate, threats low-probability |

### C3 Financials (use USD growth for hyperinflation currencies)
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| revenue_growth (25%) | declining 3+ yrs | 5y CAGR 4–8%, stable | 5y CAGR > 20% and accelerating |
| profit_growth_margins (25%) | losses / margins shrinking | profit growth ≈ revenue, margins flat | profit growth > revenue growth, margins expanding |
| earnings_quality (20%) | FCF ≪ NI, recurring "one-offs" | FCF ≈ NI, occasional 1-offs | FCF ≥ NI, clean, low SBC |
| balance_sheet (30%) | net debt/EBITDA > 4, coverage < 2 | 1–2.5×, coverage 5–10 | net cash, current ratio > 1.5 |

### C4a Valuation
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| multiples (50%) | > 50% premium to both 5y avg and peers without superior growth | in line | > 30% discount to both with comparable quality |
| fair_value_upside (50%) | fair mid ≥ 30% below price | ±5% | fair mid ≥ 40% above price |

### C4b Momentum & risk
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| expected_move_1m (35%) | ≤ −8% | 0% | ≥ +8% (linear in between) |
| news_risk (30%) | ≥ 1 H-risk negative item not priced in | mixed / M | only L risks or positive catalysts |
| manipulation (15%) | High → 1 | Medium → 5 | Low → 10 (scores.py maps L/M/H) |
| ceo_trust (20%) | = CEO scorecard score (0–10) | | |

### C5 Bank consensus (Section 5)
| Sub (weight) | 0 | 5 | 10 |
|---|---|---|---|
| rating_mix (40%) | all covered banks Sell | all Hold / mixed | all covered banks Buy (Buy = 10, Hold = 5, Sell = 0, averaged) |
| target_upside (35%) | median upside ≤ −15% | 0% | ≥ +30% (linear in between) |
| revision_trend (25%) | only cuts/downgrades in 180d | balanced or none | only raises/upgrades (10 × raises / (raises + cuts)) |

Fewer than **2** covered banks (fixed + substitute + local) → every C5 sub = **5.0** and `s5.summary_tag = "Insufficient"`.

## Horizon weights → final scores
| Component | Short (≤ 3 mo) | Medium (6–12 mo) | Long (1–3 yr) |
|---|---|---|---|
| C1 Business | 5% | 15% | 30% |
| C2 Competition | 10% | 15% | 20% |
| C3 Financials | 10% | 20% | 25% |
| C4a Valuation | 20% | 20% | 10% |
| C4b Momentum & risk | 45% | 15% | 5% |
| C5 Bank consensus | 10% | 15% | 10% |

Final = Σ(component × weight), one decimal, shown as `X.X/10`. Higher = more likely to invest.
