"""Validate <TICKER>.json sidecars: JSON schema + semantic rules from references/rules.md.

Usage: python validate_report.py stock-reports/2026-10-03/AAPL.json [more.json ...]
Exit code 1 if any ERROR. WARN lines do not fail but should be fixed.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scores import compute, from_report  # noqa: E402

SCHEMA = os.path.join(HERE, "..", "references", "report-schema.json")
BANNED = [r"\bstrong brand\b", r"\bduopoly\b", r"\bcompetition is (high|intense)\b", r"\bdepends on (the )?economy\b",
          r"\bbetter advertising\b", r"\bmacro(economic)? (risk|uncertainty)\b$", r"\bsupply chain risk\b$",
          r"\bgood management\b", r"\bmarket leader\b$", r"\binnovative products\b$"]
SHORT_FIELDS = {"cause", "driver", "note", "duration", "channel"}


def walk_L(obj, path=""):
    """Yield (path, key, {en,tr}) for every localized object."""
    if isinstance(obj, dict):
        if set(obj) == {"en", "tr"}:
            yield path, path.rsplit(".", 1)[-1], obj
            return
        for k, v in obj.items():
            yield from walk_L(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_L(v, f"{path}[{i}]")


FIXED_BANKS = ["JPMorgan", "Bank of America", "Morgan Stanley", "Goldman Sachs"]
BANNED_TOPICS = BANNED + [r"\bstrong demand\b", r"\bAI tailwinds?\b", r"\bsolid execution\b", r"\bwell[- ]positioned\b",
                          r"\battractive valuation\b", r"\bgrowth (story|outlook)\b$", r"\bstrong (results|quarter)\b$"]


def check_s5(rep: dict) -> list[str]:
    """Section 5 (bank research) rules from references/rules.md."""
    from datetime import date
    errs, s5 = [], rep["s5"]
    rows = s5["rows"]
    fixed = [r for r in rows if r["role"] == "fixed"]
    names = [r["bank"] for r in fixed]
    for b in FIXED_BANKS:
        if names.count(b) != 1:
            errs.append(f"s5: fixed bank '{b}' must appear exactly once (found {names.count(b)})")
    if len(fixed) != 4:
        errs.append(f"s5: exactly 4 fixed rows required (found {len(fixed)})")
    if sum(r["role"] == "substitute" for r in rows) > 3:
        errs.append("s5: max 3 substitute rows")
    local = [r for r in rows if r["role"] == "local"]
    if local and rep["meta"]["exchange"] != "BIST":
        errs.append("s5: local broker rows only allowed for BIST stocks")
    if len(local) > 3:
        errs.append("s5: max 3 local rows")
    try:
        ref = date.fromisoformat(rep["meta"]["report_date"][:10])
    except ValueError:
        ref = None
    price = rep["snapshot"]["price"]
    for i, r in enumerate(rows):
        tag = f"s5.rows[{i}] {r['bank']}"
        if r["covered"]:
            if not r["date"] or r["rating"] is None:
                errs.append(f"{tag}: covered rows need date and normalized rating")
            elif ref and (ref - date.fromisoformat(r["date"][:10])).days > s5["window_days"]:
                errs.append(f"{tag}: date {r['date']} older than window ({s5['window_days']}d)")
            if (r.get("target") and price and r.get("upside_pct") is not None
                    and (r.get("target_currency") in (None, rep["meta"]["currency"]))):
                exp = (r["target"] / price - 1) * 100
                if abs(exp - r["upside_pct"]) > 0.5:
                    errs.append(f"{tag}: upside_pct {r['upside_pct']} but target/price gives {exp:.2f}")
            if r["topics_status"] == "no_coverage":
                errs.append(f"{tag}: covered row cannot have topics_status 'no_coverage'")
            if r["topics_status"] == "reported" and not (r["important"] or r["niche"]):
                errs.append(f"{tag}: topics_status 'reported' but no topics")
            if r["topics_status"] == "reported" and not r.get("topic_sources"):
                errs.append(f"{tag}: reported topics need topic_sources (article URLs or source ids)")
        else:
            if r["topics_status"] != "no_coverage" or r["important"] or r["niche"] or r["rating"] or r["target"]:
                errs.append(f"{tag}: uncovered rows must be empty with topics_status 'no_coverage'")
        for k in ("important", "niche"):
            for j, L in enumerate(r[k]):
                if len(L["en"].split()) > 12:
                    errs.append(f"{tag}.{k}[{j}]: {len(L['en'].split())} words (>12)")
                for b in BANNED_TOPICS:
                    if re.search(b, L["en"], re.I):
                        errs.append(f"{tag}.{k}[{j}]: generic phrasing '{L['en'][:50]}'")
    cov = [r for r in rows if r["covered"]]
    c = s5["consensus"]
    for k, lab in (("buy", "Buy"), ("hold", "Hold"), ("sell", "Sell")):
        n = sum(r["rating"] == lab for r in cov)
        if c[k] != n:
            errs.append(f"s5.consensus.{k}={c[k]} but rows give {n}")
    if c["covered_fixed"] != sum(r["covered"] for r in fixed):
        errs.append("s5.consensus.covered_fixed does not match fixed rows")
    exp_tag = ("Insufficient" if len(cov) < 2 else "Buy-majority" if c["buy"] > len(cov) / 2
               else "Sell-majority" if c["sell"] > len(cov) / 2 else "Mixed")
    if s5["summary_tag"] != exp_tag:
        errs.append(f"s5.summary_tag={s5['summary_tag']} but rows give {exp_tag}")
    if rep["tags"].get("bank_view") not in (None, s5["summary_tag"]):
        errs.append("tags.bank_view != s5.summary_tag")
    if len(cov) < 2:
        subs = {x["key"]: x["score"] for x in rep["scores"]["components"]["C5"]["subs"]}
        if any(abs(v - 5.0) > 0.01 for v in subs.values()):
            errs.append("C5: fewer than 2 covered banks -> every C5 sub-score must be 5.0")
    return errs


def validate(path: str) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    try:
        import jsonschema
        with open(SCHEMA, encoding="utf-8") as f:
            schema = json.load(f)
        v = jsonschema.Draft202012Validator(schema)
        for e in sorted(v.iter_errors(rep), key=lambda e: list(e.path)):
            msg = e.message if len(e.message) < 160 else f"violates {e.validator}={e.validator_value!r}" +                 (f" (has {len(e.instance)})" if isinstance(e.instance, (list, dict)) else "")
            errs.append(f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {msg}")
    except ImportError:
        warns.append("jsonschema not installed - schema check skipped (pip install jsonschema)")
    if errs:
        return errs, warns  # semantic checks assume valid shape

    # scores must match the deterministic calculator
    try:
        res = compute(from_report(rep))
        for c, sc in res["components"].items():
            got = rep["scores"]["components"][c]["score"]
            if abs(got - sc) > 0.05:
                errs.append(f"scores.components.{c}.score={got} but weighted subs give {sc}")
        for h in ("short", "medium", "long"):
            if abs(rep["scores"][h] - res[h]) > 0.05:
                errs.append(f"scores.{h}={rep['scores'][h]} but scores.py gives {res[h]}")
    except Exception as e:  # noqa: BLE001
        errs.append(f"scores: {e}")

    sc = rep["s4"]["forecast_1m"]["scenarios"]
    if sorted(s["name"] for s in sc) != ["base", "bear", "bull"]:
        errs.append("forecast_1m.scenarios must be exactly bear/base/bull")
    p = sum(s["probability_pct"] for s in sc)
    if abs(p - 100) > 0.5:
        errs.append(f"forecast_1m probabilities sum to {p}, must be 100")
    ev = sum(s["probability_pct"] * s["move_pct"] for s in sc) / 100
    if abs(ev - rep["s4"]["forecast_1m"]["expected_move_pct"]) > 0.15:
        errs.append(f"expected_move_pct={rep['s4']['forecast_1m']['expected_move_pct']} but probability-weighted = {ev:.2f}")

    m = rep["s4"]["manipulation"]
    tot = sum(i["points"] for i in m["inputs"])
    if abs(tot - m["total_points"]) > 0.01:
        errs.append(f"manipulation.total_points={m['total_points']} but inputs sum to {tot}")
    lvl = "L" if tot <= 5 else "M" if tot <= 11 else "H"
    if m["level"] != lvl:
        errs.append(f"manipulation.level={m['level']} but {tot} pts -> {lvl}")
    if rep["tags"]["manipulation"] != m["level"]:
        errs.append("tags.manipulation != s4.manipulation.level")
    ceo = rep["s4"]["ceo"]
    t = "H" if ceo["score"] >= 7 else "M" if ceo["score"] >= 4 else "L"
    if ceo["trust"] != t or rep["tags"]["ceo_trust"] != t:
        errs.append(f"ceo trust must be {t} for score {ceo['score']} (s4.ceo.trust and tags.ceo_trust)")

    years = [y for y in rep["s3"]["years"] if not y.get("ttm")]
    if len(years) < 5 and not rep["s3"].get("years_missing_reason"):
        errs.append(f"s3.years has {len(years)} fiscal years (<5) and no years_missing_reason")
    if rep["meta"]["classification"] != rep["s1"]["futureproof"]["classification"]:
        errs.append("meta.classification != s1.futureproof.classification")

    for path_, key, L in walk_L(rep):
        if not L["en"].strip() or not L["tr"].strip():
            errs.append(f"{path_}: empty en/tr text")
        if L["en"] == L["tr"] and len(L["en"].split()) > 2 and not path_.startswith("sources"):
            warns.append(f"{path_}: tr identical to en (untranslated?)")
        if key in SHORT_FIELDS and len(L["en"].split()) > 12:
            warns.append(f"{path_}: {len(L['en'].split())} words (>12) - shorten")
        if key.startswith("summary_") and len(L["en"].split()) > 60:
            warns.append(f"{path_}: {len(L['en'].split())} words (>60)")
        if key in ("item", "evidence"):
            for b in BANNED:
                if re.search(b, L["en"], re.I):
                    errs.append(f"{path_}: generic/banned phrasing '{L['en'][:60]}'")
    errs += check_s5(rep)
    ids = {s["id"] for s in rep["sources"]}
    for path_, val in _sources(rep):
        if val and not val.startswith("http") and val not in ids:
            warns.append(f"{path_}: source '{val}' not in sources[]")
    if not rep["s4"]["news"]:
        warns.append("s4.news is empty - check fetch_news aliases / --days")
    return errs, warns


def _sources(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k == "source" and isinstance(v, (str, type(None))):
                yield p, v
            else:
                yield from _sources(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _sources(v, f"{path}[{i}]")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    bad = 0
    for p in sys.argv[1:]:
        errs, warns = validate(p)
        print(f"{'FAIL' if errs else 'OK  '} {p}  ({len(errs)} errors, {len(warns)} warnings)")
        for e in errs:
            print(f"  ERROR {e}")
        for w in warns[:25]:
            print(f"  WARN  {w}")
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
