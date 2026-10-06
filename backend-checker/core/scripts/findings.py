"""Findings store and report renderer. Agents write JSON; this script turns it into the report.

Subcommands (all take --root . and --check <id>):
  validate   check findings-<id>.new.json against the schema (agents run this before returning)
  merge      fold the agent's new findings into findings-<id>.json: findings in files/sections that
             were re-analyzed are replaced, the rest are carried over, fixed ones vanish; applies decisions
  questions  list 4a items that still need the user's answer (already-answered ones are filtered out)
  decide     record answers: --answers '{"<fingerprint>": "intended|report|unsure", ...}'
  render     write the markdown report (output_md from the registry)

Schema: references/findings-schema.md
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

TEXT_FIELDS = ("title", "problem", "fix", "question", "symbol")
ANSWERS = {"intended", "report", "unsure"}


def paths(root, entry):
    sid = entry["id"]
    return {
        "store": os.path.join(root, entry["findings_json"]),
        "new": os.path.join(root, entry["findings_json"].replace(".json", ".new.json")),
        "plan": C.state_path(root, f"plan-{sid}.json"),
        "decisions": C.state_path(root, "decisions.json"),
        "md": os.path.join(root, entry["output_md"]),
    }


def fingerprint(check, f):
    key = "|".join([check, str(f.get("section", "")), str(f.get("file", "")), str(f.get("symbol") or ""),
                    str(f.get("rule") or re.sub(r"\W+", "-", f.get("title", "").lower())[:40])])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def mask_finding(f):
    for k in TEXT_FIELDS:
        if isinstance(f.get(k), str):
            f[k] = C.mask_text(f[k])
        elif isinstance(f.get(k), list):
            f[k] = [C.mask_text(x) if isinstance(x, str) else x for x in f[k]]
    return f


def validate_doc(doc, entry, root):
    secs = C.load_sections(entry)
    ids = {s["id"] for s in secs["sections"]}
    levels = secs["levels"]
    errors, warnings = [], []
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        return ["top level must be an object with a 'findings' list"], []
    for k in (doc.get("section_notes") or {}):
        if k not in ids:
            errors.append(f"section_notes: unknown section '{k}'")
    for i, f in enumerate(doc["findings"]):
        where = f"findings[{i}] ({f.get('title', '?')[:40]})"
        for req in ("section", "title", "file", "problem", "fix"):
            if not f.get(req):
                errors.append(f"{where}: missing '{req}'")
        if f.get("section") not in ids:
            errors.append(f"{where}: unknown section '{f.get('section')}' (valid: {', '.join(sorted(ids))})")
        if secs["scale"] == "severity":
            if f.get("severity") not in levels:
                errors.append(f"{where}: severity must be one of {levels}")
        else:
            if f.get("impact") not in levels:
                errors.append(f"{where}: impact must be one of {levels}")
            if f.get("effort") not in secs.get("efforts", ["S", "M", "L"]):
                errors.append(f"{where}: effort must be one of S/M/L")
        if f.get("line") is not None and not isinstance(f.get("line"), int):
            errors.append(f"{where}: line must be an integer or null")
        if not isinstance(f.get("fix"), (str, list)):
            errors.append(f"{where}: fix must be a string or a list of steps")
        if f.get("needs_confirmation") and not f.get("question"):
            errors.append(f"{where}: needs_confirmation requires a 'question'")
        fp = f.get("file", "")
        if fp and not os.path.exists(os.path.join(root, fp.split(":")[0])):
            warnings.append(f"{where}: file '{fp}' does not exist (use a repo-relative path)")
        for loc in f.get("locations", []) or []:
            if not re.match(r"^[^:]+(:\d+(-\d+)?)?$", str(loc)):
                warnings.append(f"{where}: location '{loc}' should look like path:line or path:start-end")
    return errors, warnings


def cmd_validate(root, entry, quiet=False):
    p = paths(root, entry)
    doc = C.load_json(p["new"])
    if doc is None:
        print(json.dumps({"ok": False, "errors": [f"{C.rel(p['new'], root)} missing or not valid JSON"]}))
        return 1
    errors, warnings = validate_doc(doc, entry, root)
    if not quiet or errors:
        print(json.dumps({"ok": not errors, "findings": len(doc["findings"]), "errors": errors[:40], "warnings": warnings[:20]}, indent=1))
    return 1 if errors else 0


def apply_decisions(check, findings, decisions):
    out = []
    for f in findings:
        d = decisions.get(f["fingerprint"])
        if d and f.get("needs_confirmation"):
            if d["answer"] == "intended":
                continue
            f["needs_confirmation"] = False
            f["confirmed"] = d["answer"]
            if d["answer"] == "unsure":
                if "severity" in f:
                    f["severity"] = "Low"
                if "impact" in f:
                    f["impact"] = "Low"
        out.append(f)
    return out


def current_hashes(index):
    h = {p: m["sha256"] for p, m in index["files"].items()}
    h.update({p: m["sha256"] for p, m in index.get("extra_files", {}).items()})
    h.update({m["path"]: m["sha256"] for m in index.get("manifests", [])})
    return h


def cmd_merge(root, entry):
    p = paths(root, entry)
    if cmd_validate(root, entry, quiet=True):
        return 1
    plan = C.load_json(p["plan"])
    if not plan:
        print(json.dumps({"ok": False, "errors": ["plan file missing: run plan.py first"]}))
        return 1
    if os.path.getmtime(p["new"]) < os.path.getmtime(p["plan"]) - 1:
        print(json.dumps({"ok": False, "errors": [f"{C.rel(p['new'], root)} is older than this run's plan (stale output from an earlier run)"]}))
        return 1
    index = C.load_json(C.state_path(root, "index.json"))
    new = C.load_json(p["new"])
    prev = C.load_json(p["store"]) or {}
    analyzed = {f["path"] for f in plan["files_to_analyze"]}
    deleted = set(plan.get("deleted_files", []))
    rerun = set(plan.get("rerun_sections", []))
    check = entry["id"]

    kept = []
    if plan["mode"] == "incremental":
        for f in prev.get("findings", []):
            if f.get("file") in analyzed or f.get("file") in deleted or f.get("section") in rerun:
                continue
            if f.get("file") and not os.path.exists(os.path.join(root, f["file"])):
                continue
            kept.append(f)
    fresh, seen = [], {}
    for f in new["findings"]:
        f = mask_finding(dict(f))
        fp = fingerprint(check, f)
        seen[fp] = seen.get(fp, 0) + 1
        f["fingerprint"] = fp if seen[fp] == 1 else f"{fp}-{seen[fp]}"
        f.setdefault("first_seen", C.now_iso()[:10])
        fresh.append(f)
    old_by_fp = {f.get("fingerprint"): f for f in prev.get("findings", [])}
    for f in fresh:
        if f["fingerprint"] in old_by_fp:
            f["first_seen"] = old_by_fp[f["fingerprint"]].get("first_seen", f["first_seen"])
    fresh_fps = {f["fingerprint"] for f in fresh}
    merged = [f for f in kept if f.get("fingerprint") not in fresh_fps] + fresh
    decisions = C.load_json(p["decisions"], {})
    merged = apply_decisions(check, merged, decisions)

    notes = {} if plan["mode"] == "full" else {k: v for k, v in (prev.get("section_notes") or {}).items() if k not in rerun}
    for k, v in (new.get("section_notes") or {}).items():
        if v:
            notes[k] = C.mask_text(v)
        else:
            notes.pop(k, None)

    store = {
        "check": check, "generated_at": C.now_iso(), "commit": index["git"]["commit"], "dirty": index["git"]["dirty"],
        "mode": plan["mode"], "files_analyzed": len(analyzed), "carried_over": len(kept),
        "api_path": index["api_path"], "extra_paths": index.get("extra_paths", []),
        "stack": index.get("stack"), "runtime": index.get("runtime"),
        "file_hashes": current_hashes(index), "section_notes": notes, "findings": merged,
    }
    C.save_json(p["store"], store)
    os.remove(p["new"])
    q = [f for f in merged if f.get("needs_confirmation") and f["fingerprint"] not in decisions]
    print(json.dumps({"ok": True, "findings": len(merged), "new_or_updated": len(fresh), "carried_over": len(kept),
                      "open_questions": len(q)}, indent=1))
    return 0


def cmd_questions(root, entry):
    p = paths(root, entry)
    store = C.load_json(p["store"], {"findings": []})
    decisions = C.load_json(p["decisions"], {})
    qs = [{"fingerprint": f["fingerprint"], "section": f["section"], "title": f["title"],
           "where": f"{f['file']}:{f.get('line') or ''}".rstrip(":"), "question": f["question"]}
          for f in store["findings"] if f.get("needs_confirmation") and f["fingerprint"] not in decisions]
    print(json.dumps({"questions": qs}, ensure_ascii=False, indent=1))
    return 0


def cmd_decide(root, entry, answers):
    p = paths(root, entry)
    store = C.load_json(p["store"], {"findings": []})
    by_fp = {f["fingerprint"]: f for f in store["findings"]}
    decisions = C.load_json(p["decisions"], {})
    bad = {k: v for k, v in answers.items() if v not in ANSWERS or k not in by_fp}
    if bad:
        print(json.dumps({"ok": False, "errors": [f"{k}: answer must be one of {sorted(ANSWERS)} and the fingerprint must exist" for k in bad]}))
        return 1
    for fp, ans in answers.items():
        f = by_fp[fp]
        decisions[fp] = {"answer": ans, "check": entry["id"], "title": f["title"], "file": f["file"], "answered_at": C.now_iso()}
    C.save_json(p["decisions"], decisions)
    store["findings"] = apply_decisions(entry["id"], store["findings"], decisions)
    C.save_json(p["store"], store)
    print(json.dumps({"ok": True, "recorded": len(answers), "remaining_findings": len(store["findings"])}))
    return 0

# --------------------------------------------------------------------------- render

def link(md_dir, root, file, line=None, end=None):
    label = file + (f":{line}" if line else "") + (f"-{end}" if end else "")
    if not os.path.exists(os.path.join(root, file)):  # e.g. a file that only exists in git history
        return f"`{label}`"
    target = os.path.relpath(os.path.join(root, file), md_dir).replace("\\", "/")
    return f"[`{label}`]({target}" + (f"#L{line}" if line else "") + ")"


def loc_link(md_dir, root, loc):
    m = re.match(r"^(.+?):(\d+)(?:-(\d+))?$", str(loc))
    if m:
        return link(md_dir, root, m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None)
    return link(md_dir, root, str(loc))


def fmt_fix(fix, label):
    if isinstance(fix, list):
        return f"**{label}:**\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(fix, 1))
    return f"**{label}:** {fix}"


def stack_line(store):
    st = store.get("stack") or {}
    bits = [f"{r['product']} {r['version']}" for r in (store.get("runtime") or [])[:1]]
    bits += [f"{f['name']} {f['version']}" for f in st.get("frameworks", [])]
    bits += [f"{f['name']} {f['version']}" for f in st.get("data", [])]
    if not bits:
        bits = list((st.get("languages") or {}).keys())
    return " · ".join(bits) or "unknown"


def cmd_render(root, entry):
    p = paths(root, entry)
    store = C.load_json(p["store"])
    if not store:
        print(json.dumps({"ok": False, "errors": ["no findings store yet: run merge first"]}))
        return 1
    plan = C.load_json(p["plan"], {})
    secs = C.load_sections(entry)
    severity = secs["scale"] == "severity"
    levels = secs["levels"]
    md_dir = os.path.dirname(p["md"])
    os.makedirs(md_dir, exist_ok=True)
    findings = store["findings"]
    rank = {lv: i for i, lv in enumerate(levels)}
    by_sec = {}
    for f in findings:
        by_sec.setdefault(f["section"], []).append(f)
    for v in by_sec.values():
        v.sort(key=lambda f: (rank.get(f.get("severity") or f.get("impact"), 9), f.get("file", ""), f.get("line") or 0))
    ids = {}
    for s in secs["sections"]:
        for i, f in enumerate(by_sec.get(s["id"], []), 1):
            ids[f["fingerprint"]] = f"{s['id']}.{i}"

    when = (store.get("generated_at") or "")[:16].replace("T", " ")
    commit = store.get("commit") or "no git"
    dirty = " (with uncommitted changes)" if store.get("dirty") else ""
    if plan.get("skip"):
        mode = "no source changes since the last run, report re-rendered from stored findings"
    elif store.get("mode") == "incremental":
        mode = f"incremental run: {store.get('files_analyzed', 0)} file(s) re-analyzed, {store.get('carried_over', 0)} finding(s) carried over"
    else:
        mode = "full run"
    scope = f"`{store['api_path']}/`" + (" · extra context: " + ", ".join(f"`{x.rstrip('/')}/`" for x in store.get("extra_paths", [])) if store.get("extra_paths") else "")
    L = [f"# {secs['title']}", "",
         f"> Generated {when} · commit `{commit}`{dirty} · {mode}",
         f"> Scope: {scope} · Stack: {stack_line(store)}",
         "> This file is rewritten on every run and is gitignored. Fixed problems disappear from it.", ""]

    # Summary table
    L += ["## Summary", ""]
    head = levels + ["Total"]
    L.append("| Section | " + " | ".join(head) + " |")
    L.append("|---|" + "---:|" * len(head))
    totals = {lv: 0 for lv in levels}
    for s in secs["sections"]:
        fs = by_sec.get(s["id"], [])
        counts = {lv: sum(1 for f in fs if (f.get("severity") if severity else f.get("impact")) == lv) for lv in levels}
        for lv in levels:
            totals[lv] += counts[lv]
        cells = [str(counts[lv]) if counts[lv] else "–" for lv in levels] + [f"**{len(fs)}**" if fs else "–"]
        L.append(f"| {s['id']}. {s['title']} | " + " | ".join(cells) + " |")
    L.append("| **Total** | " + " | ".join(f"**{totals[lv]}**" for lv in levels) + f" | **{len(findings)}** |")
    L.append("")
    open_q = [f for f in findings if f.get("needs_confirmation")]
    if open_q:
        L += [f"**{len(open_q)} item(s) need your answer** (marked *Needs your answer* in section 4a). Answer them on the next run.", ""]
    if severity:
        top = [f for f in findings if f.get("severity") in ("Critical",)][:5] or [f for f in findings if f.get("severity") == "High"][:5]
        if top:
            L += ["**Fix first:** " + "; ".join(f"{ids[f['fingerprint']]} {f['title']}" for f in top), ""]

    groups = {g["id"]: g["title"] for g in secs.get("groups", [])}
    printed_groups = set()
    notes = store.get("section_notes") or {}
    for s in secs["sections"]:
        g = s.get("group")
        if g and g not in printed_groups:
            printed_groups.add(g)
            L += [f"## {g}. {groups.get(g, '')}", ""]
        L += [f"{'###' if g else '##'} {s['id']}. {s['title']}", ""]
        fs = by_sec.get(s["id"], [])
        note = notes.get(s["id"])
        if note and not (fs and re.match(r"(?i)^(not applicable|no issues)", note)):
            L += [note, ""]
        if not fs:
            if not note:
                L += ["No issues found.", ""]
            continue
        hl = "####"  # same level everywhere so findings are easy to find/grep
        for f in fs:
            lvl = f.get("severity") if severity else f.get("impact")
            tag = f"{lvl}" if severity else f"Impact {lvl} · Effort {f.get('effort')}"
            L.append(f"{hl} {ids[f['fingerprint']]} · {tag} · {f['title']}")
            L.append("")
            meta = [link(md_dir, root, f["file"], f.get("line"))]
            if f.get("symbol"):
                meta.append(f"`{f['symbol']}`")
            if f.get("owasp"):
                meta.append(f["owasp"])
            L.append(" · ".join(meta))
            if f.get("locations"):
                L.append("Also: " + ", ".join(loc_link(md_dir, root, x) for x in f["locations"][:12]))
            L.append("")
            if f.get("needs_confirmation"):
                L += [f"**Needs your answer:** {f['question']}", ""]
            L += [f"**Problem:** {f['problem']}", "", fmt_fix(f["fix"], "Fix" if severity else "Plan"), ""]

    iv = {"High": 3, "Medium": 2, "Low": 1}
    ev = {"S": 1, "M": 2, "L": 3}
    scored = sorted(findings, key=lambda f: (-(iv.get(f.get("impact"), 1) / ev.get(f.get("effort"), 2)), ids[f["fingerprint"]]))
    if secs.get("roadmap") and findings:
        L += ["## Refactor roadmap", "", "Ordered by impact ÷ effort. Items in the same group are best done together.", ""]
        done, n = set(), 0
        for f in scored:
            if f["fingerprint"] in done:
                continue
            grp = f.get("group")
            members = [x for x in scored if grp and x.get("group") == grp] or [f]
            n += 1
            if len(members) > 1:
                L.append(f"{n}. **{grp}**")
                for x in members:
                    L.append(f"   - {ids[x['fingerprint']]} {x['title']} (impact {x.get('impact')}, effort {x.get('effort')})")
                    done.add(x["fingerprint"])
            else:
                L.append(f"{n}. {ids[f['fingerprint']]} {f['title']} (impact {f.get('impact')}, effort {f.get('effort')})")
                done.add(f["fingerprint"])
        L.append("")

    text = C.mask_text("\n".join(L).rstrip() + "\n")
    with open(p["md"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    summary = {lv: totals[lv] for lv in levels}
    # Everything the orchestrator's reply needs, so it never has to read the report back.
    if severity:
        order = {s["id"]: i for i, s in enumerate(secs["sections"])}
        top = sorted(findings, key=lambda f: (rank.get(f.get("severity"), 9), order.get(f["section"], 99),
                                              int(ids[f["fingerprint"]].rsplit(".", 1)[1])))[:5]
    else:
        top = scored[:3]
    out = {"ok": True, "report": C.rel(p["md"], root), "mode": mode, "findings": len(findings), "by_level": summary,
           "open_questions": len(open_q),
           "top": [f"{ids[f['fingerprint']]} [{f.get('severity') or f.get('impact')}] {f['title']}" for f in top]}
    if entry.get("needs_tests"):
        t = C.load_json(C.state_path(root, "tests.json")) or {}
        out["tests"] = notes.get("3") or t.get("status") or "not run"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["validate", "merge", "questions", "decide", "render"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", required=True)
    ap.add_argument("--answers", help='JSON object {"fingerprint": "intended|report|unsure"}')
    ap.add_argument("--answers-file")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    entry = C.registry_entry(a.check)
    if a.command == "validate":
        return cmd_validate(root, entry)
    if a.command == "merge":
        return cmd_merge(root, entry)
    if a.command == "questions":
        return cmd_questions(root, entry)
    if a.command == "decide":
        ans = json.loads(a.answers) if a.answers else C.load_json(a.answers_file, {})
        return cmd_decide(root, entry, ans or {})
    return cmd_render(root, entry)


if __name__ == "__main__":
    sys.exit(main())
