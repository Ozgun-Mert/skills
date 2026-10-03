"""5 fiscal years + TTM of income statement, balance sheet and cash flow.

Usage: python fetch_financials.py --tv NASDAQ:AAPL --yahoo AAPL [--cik 320193] [--years 5] [--out ...]

Source priority per field and year:
  US (has CIK): SEC EDGAR XBRL companyfacts (official) > TradingView > Yahoo
  Others:       TradingView > Yahoo   (agent adds KAP / company IR figures by hand, citing URL)
Revenue is cross-checked between the top two sources (> 2% diff -> discrepancy).
Segment revenue is NOT in companyfacts - the agent reads it from the 10-K/annual report.
"""
from __future__ import annotations

import argparse
from datetime import date

from common import cagr, http, now_iso, pct_change, tv_scan, write_json

FIELDS = ["revenue", "gross_profit", "operating_income", "ebitda", "net_income", "eps_diluted",
          "rnd", "sbc", "cash", "total_debt", "equity", "current_assets", "current_liabilities",
          "goodwill", "total_assets", "cfo", "capex", "fcf", "buybacks", "dividends_paid",
          "interest_expense", "d_and_a"]

EDGAR_CONCEPTS = {  # first concept found wins, per year
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "goodwill": ["Goodwill"],
    "total_assets": ["Assets"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "d_and_a": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                "DepreciationAmortizationAndAccretionNet"],
}
INSTANT = {"cash", "equity", "current_assets", "current_liabilities", "goodwill", "total_assets"}

TV_HIST = {"revenue": "total_revenue_fy_h", "gross_profit": "gross_profit_fy_h", "net_income": "net_income_fy_h",
           "ebitda": "ebitda_fy_h", "eps_diluted": "earnings_per_share_diluted_fy_h", "fcf": "free_cash_flow_fy_h",
           "total_debt": "total_debt_fy_h", "total_assets": "total_assets_fy_h"}
TV_TTM = {"revenue": "total_revenue_ttm", "gross_profit": "gross_profit_ttm", "operating_income": "oper_income_ttm",
          "ebitda": "ebitda_ttm", "net_income": "net_income_ttm", "eps_diluted": "earnings_per_share_diluted_ttm",
          "fcf": "free_cash_flow_ttm", "rnd": "research_and_dev_ttm", "capex": "capital_expenditures_ttm",
          "cfo": "cash_f_operating_activities_ttm"}
TV_LATEST_Q = {"cash": "cash_n_short_term_invest_fq", "equity": "total_equity_fq",
               "current_assets": "total_current_assets_fq", "current_liabilities": "total_current_liabilities_fq",
               "goodwill": "goodwill_fq", "net_debt": "net_debt_fq", "current_ratio": "current_ratio_fq",
               "debt_to_equity": "debt_to_equity_fq"}

YF_ROWS = {
    "revenue": ["Total Revenue"], "gross_profit": ["Gross Profit"], "operating_income": ["Operating Income"],
    "ebitda": ["EBITDA", "Normalized EBITDA"], "net_income": ["Net Income", "Net Income Common Stockholders"],
    "eps_diluted": ["Diluted EPS"], "rnd": ["Research And Development"],
    "interest_expense": ["Interest Expense"], "d_and_a": ["Reconciled Depreciation"],
    "cash": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "total_debt": ["Total Debt"], "equity": ["Stockholders Equity", "Common Stock Equity"],
    "current_assets": ["Current Assets"], "current_liabilities": ["Current Liabilities"],
    "goodwill": ["Goodwill"], "total_assets": ["Total Assets"],
    "cfo": ["Operating Cash Flow"], "capex": ["Capital Expenditure"], "fcf": ["Free Cash Flow"],
    "buybacks": ["Repurchase Of Capital Stock"], "dividends_paid": ["Cash Dividends Paid"],
    "sbc": ["Stock Based Compensation"],
}


def cik_lookup(ticker: str) -> str | None:
    r = http("GET", "https://www.sec.gov/files/company_tickers.json", sec=True)
    for row in r.json().values():
        if row["ticker"].upper() == ticker.upper():
            return str(row["cik_str"])
    return None


def edgar(cik: str) -> tuple[dict, str]:
    cik10 = str(int(cik)).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
    facts = http("GET", url, sec=True).json().get("facts", {}).get("us-gaap", {})
    out: dict[int, dict] = {}
    # GOTCHA: companies switch concepts over time (NVDA: RevenueFromContract... -> Revenues),
    # so merge per year: the highest-priority concept that has a value for that year wins.
    for field, concepts in EDGAR_CONCEPTS.items():
        for prio, concept in enumerate(concepts):
            c = facts.get(concept)
            if not c:
                continue
            for unit, rows in c.get("units", {}).items():
                for r in rows:
                    if r.get("form") not in ("10-K", "10-K/A", "20-F", "40-F") or r.get("fp") != "FY":
                        continue
                    end = date.fromisoformat(r["end"])
                    if field not in INSTANT:
                        if not r.get("start"):
                            continue
                        days = (end - date.fromisoformat(r["start"])).days
                        if not 330 <= days <= 400:
                            continue
                    fy = end.year
                    cur = out.setdefault(fy, {}).get(field)
                    # lower prio index wins; same concept -> latest filing (restatements) wins
                    if cur is None or prio < cur["prio"] or (prio == cur["prio"] and r["filed"] > cur["filed"]):
                        out[fy][field] = {"value": r["val"], "concept": concept, "prio": prio, "filed": r["filed"],
                                          "period_end": r["end"], "unit": unit}
    return out, url


def tradingview(tv: str) -> dict:
    cols = ["fiscal_period_fy_h", "currency", "fundamental_currency_code"] + list(TV_HIST.values()) \
        + list(TV_TTM.values()) + list(TV_LATEST_Q.values())
    return tv_scan([tv], cols).get(tv) or {}


def fx_history(src_cur: str, dst_cur: str) -> dict[int, dict]:
    """{year: {"avg": rate, "end": rate}} converting src -> dst (Yahoo FX history)."""
    import yfinance as yf
    h = yf.Ticker(f"{src_cur}{dst_cur}=X").history(period="10y", interval="1d")
    out: dict[int, dict] = {}
    for y in sorted(set(h.index.year)):
        c = h[h.index.year == y]["Close"]
        out[y] = {"avg": float(c.mean()), "end": float(c.iloc[-1])}
    return out


def yahoo(sym: str) -> tuple[dict[int, dict], str | None]:
    import yfinance as yf
    t = yf.Ticker(sym)
    try:
        cur = t.info.get("financialCurrency")
    except Exception:  # noqa: BLE001
        cur = None
    out: dict[int, dict] = {}
    for df in (t.income_stmt, t.balance_sheet, t.cashflow):
        if df is None or df.empty:
            continue
        for col in df.columns:
            fy = col.year
            for field, rows in YF_ROWS.items():
                for row in rows:
                    if row in df.index:
                        v = df.at[row, col]
                        if v == v and v is not None:  # not NaN
                            out.setdefault(fy, {}).setdefault(field, float(v))
                            break
    return out, cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--cik")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"fetched_at": now_iso(), "tv_symbol": a.tv, "errors": [], "discrepancies": [], "sources": {}}
    exch, ticker = a.tv.split(":", 1)
    us = exch in ("NASDAQ", "NYSE", "AMEX", "NYSE ARCA", "CBOE")

    ed, tvd, yd = {}, {}, {}
    if us:
        try:
            cik = a.cik or cik_lookup(ticker)
            if cik:
                ed, url = edgar(cik)
                out["sources"]["edgar"] = {"name": "SEC EDGAR XBRL companyfacts (10-K)", "url": url}
            else:
                out["errors"].append("EDGAR: CIK not found")
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"EDGAR: {e}")
    try:
        tvd = tradingview(a.tv)
        out["sources"]["tradingview"] = {"name": "TradingView financials",
                                         "url": f"https://www.tradingview.com/symbols/{a.tv.replace(':', '-')}/financials-overview/"}
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"TradingView: {e}")
    try:
        yd, ycur = yahoo(a.yahoo)
        out["sources"]["yahoo"] = {"name": "Yahoo Finance statements",
                                   "url": f"https://finance.yahoo.com/quote/{a.yahoo}/financials"}
    except Exception as e:  # noqa: BLE001
        ycur = None
        out["errors"].append(f"Yahoo: {e}")

    out["currency"] = tvd.get("fundamental_currency_code") or tvd.get("currency") or ycur
    # GOTCHA: Yahoo may report in the company's functional currency (THYAO -> USD) while
    # TradingView reports in the listing currency (TRY). Never mix: translate Yahoo values
    # (flows @ FY-average FX, balance-sheet items @ FY-end FX, per IAS 21).
    if yd and ycur and out["currency"] and ycur != out["currency"]:
        try:
            fx = fx_history(ycur, out["currency"])
            for fy, row in yd.items():
                r = fx.get(fy)
                if not r:
                    yd[fy] = {}
                    continue
                for f in list(row):
                    if f == "eps_diluted":
                        row[f] = row[f] * r["avg"]
                    else:
                        row[f] = row[f] * (r["end"] if f in INSTANT or f in ("total_debt",) else r["avg"])
            out["sources"]["yahoo"]["note"] = f"translated {ycur}->{out['currency']} (flows FY-avg FX, balances FY-end FX)"
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"Yahoo FX translation {ycur}->{out['currency']} failed, Yahoo values dropped: {e}")
            yd = {}
    tv_years = tvd.get("fiscal_period_fy_h") or []
    tv_by_year: dict[int, dict] = {}
    for f, col in TV_HIST.items():
        arr = tvd.get(col) or []
        for i, fy in enumerate(tv_years):
            if i < len(arr) and arr[i] is not None:
                tv_by_year.setdefault(int(fy), {})[f] = arr[i]

    # GOTCHA: TradingView labels a fiscal year by its *start* calendar year for non-December
    # year-ends (NVDA FY ending Jan-2026 -> "2025"); EDGAR/Yahoo use the period-end year.
    # Find the label shift that best matches revenue against EDGAR/Yahoo and apply it.
    ref = {y: d["revenue"]["value"] for y, d in ed.items() if "revenue" in d}
    for y, d in yd.items():
        ref.setdefault(y, d.get("revenue"))
    best_shift, best_hits = 0, -1
    for shift in (0, 1, -1):
        hits = sum(1 for y, d in tv_by_year.items() if d.get("revenue") and ref.get(y + shift)
                   and abs(d["revenue"] / ref[y + shift] - 1) < 0.02)
        if hits > best_hits:
            best_shift, best_hits = shift, hits
    if best_shift:
        tv_by_year = {y + best_shift: d for y, d in tv_by_year.items()}
        out["tv_fy_label_shift"] = best_shift
    if best_hits == 0 and ref and tv_by_year:
        out["errors"].append("TradingView fiscal years could not be aligned with EDGAR/Yahoo by revenue")

    all_years = sorted(set(ed) | set(tv_by_year) | set(yd), reverse=True)
    # Only keep years that have revenue somewhere; take the latest N (+1 for YoY base).
    all_years = [y for y in all_years if any(src.get(y, {}).get("revenue") is not None for src in (
        {k: {f: v["value"] for f, v in d.items()} for k, d in ed.items()}, tv_by_year, yd))]
    keep = all_years[: a.years + 1]

    # GOTCHA (BIST, IAS 29 / TMS 29 hyperinflation): Yahoo carries prior years restated into
    # current purchasing power, TradingView the as-reported nominal figures (ASELS 2022 revenue
    # differs ~90%). Mixing them inside one row corrupts margins, so Yahoo-only fields are
    # rescaled to the row's primary revenue basis when revenue differs by > 5%.
    rescale: dict[int, float] = {}
    for fy in keep:
        prim = (ed.get(fy, {}).get("revenue") or {}).get("value") or tv_by_year.get(fy, {}).get("revenue")
        yrev = yd.get(fy, {}).get("revenue")
        if prim and yrev and abs(prim / yrev - 1) > 0.05:
            rescale[fy] = prim / yrev
    if rescale:
        out["basis_note"] = ("Yahoo values rescaled to primary-source revenue basis (likely IAS 29 restatement "
                             "or reporting-basis difference): " + ", ".join(f"FY{y} x{f:.3f}" for y, f in sorted(rescale.items())))

    annual = []
    for fy in keep:
        row, src = {"fy": fy}, {}
        for f in FIELDS:
            chain = []
            if fy in ed and f in ed[fy]:
                chain.append(("edgar", ed[fy][f]["value"]))
            if f in tv_by_year.get(fy, {}):
                chain.append(("tradingview", tv_by_year[fy][f]))
            if f in yd.get(fy, {}):
                if fy in rescale and f != "revenue":
                    chain.append((f"yahoo(x{rescale[fy]:.3f})", yd[fy][f] * (1 if f == "eps_diluted" else rescale[fy])))
                else:
                    chain.append(("yahoo", yd[fy][f]))
            if f == "eps_diluted":
                # GOTCHA: EDGAR EPS for older years is pre-split (NVDA 4:1 2021, 10:1 2024);
                # TradingView/Yahoo EPS is split-adjusted, so they take precedence.
                chain.sort(key=lambda c: c[0] == "edgar")
            if chain:
                row[f], src[f] = chain[0][1], chain[0][0]
                if f == "revenue" and len(chain) > 1:
                    d = pct_change(chain[1][1], chain[0][1])
                    if d is not None and abs(d) > 2:
                        out["discrepancies"].append({"fy": fy, "field": f, chain[0][0]: chain[0][1],
                                                     chain[1][0]: chain[1][1], "diff_pct": d, "used": chain[0][0]})
            else:
                row[f] = None
        # derived
        if row.get("fcf") is None and row.get("cfo") is not None and row.get("capex") is not None:
            row["fcf"], src["fcf"] = row["cfo"] - abs(row["capex"]), "derived(cfo-capex)"
        if row.get("ebitda") is None and row.get("operating_income") is not None and row.get("d_and_a") is not None:
            row["ebitda"], src["ebitda"] = row["operating_income"] + row["d_and_a"], "derived(op+D&A)"
        rev = row.get("revenue")
        for f, m in (("gross_profit", "gross_margin_pct"), ("operating_income", "op_margin_pct"),
                     ("net_income", "net_margin_pct"), ("fcf", "fcf_margin_pct"), ("rnd", "rnd_pct")):
            row[m] = round(abs(row[f]) / rev * 100 if f == "rnd" else row[f] / rev * 100, 2) \
                if rev and row.get(f) is not None else None
        if row.get("current_assets") and row.get("current_liabilities"):
            row["current_ratio"] = round(row["current_assets"] / row["current_liabilities"], 2)
        if row.get("operating_income") is not None and row.get("interest_expense"):
            row["interest_coverage"] = round(row["operating_income"] / abs(row["interest_expense"]), 2)
        if row.get("total_debt") is not None and row.get("cash") is not None:
            row["net_debt"] = row["total_debt"] - row["cash"]
            if row.get("ebitda"):
                row["net_debt_to_ebitda"] = round(row["net_debt"] / row["ebitda"], 2)
        if row.get("equity") and row.get("total_assets"):
            row["equity_ratio_pct"] = round(row["equity"] / row["total_assets"] * 100, 2)
        row["_source"] = src
        annual.append(row)

    # YoY
    for i, row in enumerate(annual):
        prev = annual[i + 1] if i + 1 < len(annual) else None
        for f in ("revenue", "gross_profit", "operating_income", "net_income", "eps_diluted", "fcf", "ebitda"):
            row[f"{f}_yoy_pct"] = pct_change(row.get(f), prev.get(f)) if prev else None
    # Hyperinflation / FX guard: USD-translated revenue & net income (FY-average FX) so
    # agents can separate real growth from currency debasement (e.g. TRY, ARS).
    if out["currency"] and out["currency"] != "USD":
        try:
            fxu = fx_history(out["currency"], "USD")
            for row in annual:
                r = fxu.get(row["fy"])
                for f in ("revenue", "net_income"):
                    row[f"{f}_usd"] = round(row[f] * r["avg"], 0) if r and row.get(f) is not None else None
            for i, row in enumerate(annual):
                prev = annual[i + 1] if i + 1 < len(annual) else None
                for f in ("revenue_usd", "net_income_usd"):
                    row[f"{f}_yoy_pct"] = pct_change(row.get(f), prev.get(f)) if prev else None
            out["sources"]["fx_usd"] = {"name": f"Yahoo {out['currency']}USD=X FY-average", "url": f"https://finance.yahoo.com/quote/{out['currency']}USD=X"}
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"USD translation failed: {e}")
    out["annual"] = annual[: a.years]  # newest first; extra year only used as YoY base
    out["years_available"] = len(out["annual"])
    if out["years_available"] < a.years:
        out["errors"].append(f"only {out['years_available']} fiscal years available from all sources")

    growth = {}
    for f in ("revenue", "gross_profit", "operating_income", "net_income", "eps_diluted", "fcf",
              "revenue_usd", "net_income_usd"):
        if not any(r.get(f) is not None for r in annual):
            continue
        vals = [r.get(f) for r in annual]
        def g(n):
            return cagr(vals[0], vals[n], n) if len(vals) > n else None
        growth[f] = {"cagr_5y": g(5) if len(vals) > 5 else g(len(vals) - 1) if len(vals) > 1 else None,
                     "cagr_5y_years": min(5, len(vals) - 1), "cagr_3y": g(3),
                     "last_yoy": annual[0].get(f"{f}_yoy_pct") if annual else None}
    out["growth"] = growth

    ttm = {f: tvd.get(c) for f, c in TV_TTM.items()}
    ttm.update({f: tvd.get(c) for f, c in TV_LATEST_Q.items()})
    if ttm.get("revenue"):
        for f, m in (("gross_profit", "gross_margin_pct"), ("operating_income", "op_margin_pct"),
                     ("net_income", "net_margin_pct"), ("fcf", "fcf_margin_pct")):
            ttm[m] = round(ttm[f] / ttm["revenue"] * 100, 2) if ttm.get(f) is not None else None
    ttm["_source"] = "tradingview"
    out["ttm"] = ttm
    write_json(a.out, out)


if __name__ == "__main__":
    main()
