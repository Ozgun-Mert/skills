"""Decide what each check must analyze this run (incremental by default).

For every requested check it compares the current index.json with the file hashes stored in that
check's findings-<id>.json (the baseline from its last successful run) and writes
docs/.backend-checks/plan-<id>.json:
  files_to_analyze  changed/new files + files importing them + files of findings whose related files changed
  rerun_sections    cross-cutting sections whose inputs changed (old findings there are dropped)
  hotspots          line hints for files_to_analyze; whole-scope hints for rerun sections
  skip              nothing changed -> re-render from stored findings, spawn no agent
It also writes plan.json with the union of files (the health-mode preload set) and prep commands.

Usage: python plan.py --root . --checks security,code-quality|all [--full] [--preload-budget 120000]
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OSV_MAX_AGE_DAYS = 7


def osv_stale(root):
    d = C.load_json(C.state_path(root, "deps.json"))
    if not d or not d.get("checked_at") or not d.get("network_ok"):
        return True
    try:
        t = dt.datetime.fromisoformat(d["checked_at"])
    except ValueError:
        return True
    return (dt.datetime.now(t.tzinfo) - t).days >= OSV_MAX_AGE_DAYS


def importers_of(files, targets):
    out = set()
    for p, meta in files.items():
        if set(meta.get("imports", [])) & targets:
            out.add(p)
    return out


def plan_check(root, entry, index, full, stale):
    files = index["files"]
    src = {p for p, m in files.items() if not m.get("test")}
    prev = C.load_json(os.path.join(root, entry["findings_json"]))
    hot = index.get("hotspots", {})
    ehot = index.get("extra_hotspots", {})
    sections = [s["id"] for s in C.load_sections(entry)["sections"]]
    cross = entry.get("cross_cutting_sections", {})

    cur_hashes = {p: m["sha256"] for p, m in files.items()}
    cur_hashes.update({p: m["sha256"] for p, m in index.get("extra_files", {}).items()})
    cur_hashes.update({m["path"]: m["sha256"] for m in index.get("manifests", [])})

    if full or not prev or not prev.get("file_hashes"):
        mode = "full"
        analyze = set(src)
        why = {p: "full run" for p in analyze}
        changed, deleted = set(cur_hashes), set()
        rerun = list(sections)
        carried = 0
    else:
        mode = "incremental"
        base = prev["file_hashes"]
        changed = {p for p, h in cur_hashes.items() if base.get(p) != h}
        deleted = {p for p in base if p not in cur_hashes}
        why = {p: "changed" for p in changed & src}
        for p in importers_of(files, changed | deleted) & src:
            why.setdefault(p, "imports a changed file")
        for f in prev.get("findings", []):
            rel_files = set(f.get("related_files") or [])
            if rel_files & (changed | deleted) and f.get("file") in src:
                why.setdefault(f["file"], "has a finding whose related file changed")
        analyze = set(why)
        rerun = []
        changed_src = changed | deleted
        for sec, triggers in cross.items():
            fire = False
            for t in triggers:
                if t == "any":
                    fire = fire or bool(changed_src)
                elif t == "manifests":
                    fire = fire or any(m["path"] in changed_src for m in index.get("manifests", [])) or \
                        any(p.rsplit("/", 1)[-1] in C.MANIFEST_NAMES for p in deleted)
                elif t == "osv_stale":
                    fire = fire or stale
                elif t == "extra":
                    fire = fire or any(p in changed_src for p in index.get("extra_files", {})) or \
                        any(p not in files and p in deleted for p in deleted)
                elif t == "config":
                    fire = fire or any(files.get(p, {}).get("lang") == "config" for p in changed) or \
                        any(C.CONFIG_NAMES.search(p) for p in deleted)
                else:
                    in_cat = set(hot.get(t, {})) | set(ehot.get(t, {}))
                    old_cat = {f["file"] for f in prev.get("findings", []) if f.get("section") == sec}
                    fire = fire or bool((in_cat | old_cat) & changed_src)
            if fire:
                rerun.append(sec)
        if entry.get("needs_tests") and changed and "3" in sections:
            rerun.append("3")
        carried = sum(1 for f in prev.get("findings", [])
                      if f.get("file") not in analyze and f.get("file") not in deleted and f.get("section") not in rerun)

    keys = entry.get("hotspot_keys", [])
    hotspots = {}
    for k in keys:
        sub = {p: lines for p, lines in hot.get(k, {}).items() if p in analyze}
        if sub:
            hotspots[k] = sub
    section_hotspots = {}
    if mode == "incremental":
        for sec in rerun:
            cats = [t for t in cross.get(sec, []) if t in hot or t in ehot]
            sh = {}
            for t in cats:
                merged = dict(hot.get(t, {}))
                merged.update(ehot.get(t, {}))
                if merged:
                    sh[t] = merged
            if sh:
                section_hotspots[sec] = sh
    extra_hotspots = {k: v for k, v in ehot.items() if k in entry.get("extra_hotspot_keys", [])}

    skip = mode == "incremental" and not analyze and not rerun and not deleted
    plan = {
        "check": entry["id"],
        "title": entry["title"],
        "generated_at": C.now_iso(),
        "mode": mode,
        "skip": skip,
        "api_path": index["api_path"],
        "extra_paths": index.get("extra_paths", []),
        "files_to_analyze": [{"path": p, "lines": files[p]["lines"], "tokens": files[p]["tokens"], "why": why.get(p, "")} for p in sorted(analyze)],
        "deleted_files": sorted(deleted),
        "rerun_sections": rerun if mode == "incremental" else sections,
        "carried_findings": carried,
        "hotspots": hotspots,
        "section_hotspots": section_hotspots,
        "extra_hotspots": extra_hotspots,
        "run_tests": bool(entry.get("needs_tests")) and (mode == "full" or "3" in rerun),
        "tests": index.get("tests"),
        "stack": index.get("stack"),
        "runtime": index.get("runtime"),
        "core_dir": C.CORE_DIR.replace("\\", "/"),
        "agent_brief": os.path.join(C.CORE_DIR, entry["agent_brief"]).replace("\\", "/"),
        "new_findings_file": entry["findings_json"].replace(".json", ".new.json"),
    }
    prep = []
    for pr in entry.get("prep", []):
        when = pr.get("when_sections", ["*"])
        if not skip and ("*" in when or set(when) & set(plan["rerun_sections"]) or mode == "full"):
            script = os.path.join(C.CORE_DIR, "scripts", pr["script"]).replace("\\", "/")
            prep.append(" ".join([f'python "{script}"', "--root .", f"--plan {C.STATE_DIR}/plan-{entry['id']}.json".replace("\\", "/")] + pr.get("args", [])))
    plan["prep_commands"] = prep
    if "secrets" in keys:
        plan["secrets"] = index.get("secrets")
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--checks", default="all")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--preload-budget", type=int, default=120_000,
                    help="max estimated tokens the orchestrator preloads before forking agents (health mode)")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"))
    if not index:
        print(json.dumps({"error": "index.json missing: run index.py first"}))
        return 2
    reg = C.load_registry()
    ids = [c["id"] for c in reg] if a.checks in ("all", "*") else [x.strip() for x in a.checks.split(",") if x.strip()]
    stale = osv_stale(root)
    plans = []
    for cid in ids:
        entry = C.registry_entry(cid)
        p = plan_check(root, entry, index, a.full, stale)
        C.save_json(C.state_path(root, f"plan-{cid}.json"), p)
        plans.append(p)

    union = {}
    for p in plans:
        if not p["skip"]:
            for f in p["files_to_analyze"]:
                union[f["path"]] = f["tokens"]
    total = sum(union.values())
    summary = {
        "checks": [{
            "id": p["check"], "mode": p["mode"], "skip": p["skip"], "files_to_analyze": len(p["files_to_analyze"]),
            "tokens": sum(f["tokens"] for f in p["files_to_analyze"]),
            "rerun_sections": "all" if p["mode"] == "full" else p["rerun_sections"],
            "deleted_files": len(p["deleted_files"]), "carried_findings": p["carried_findings"], "run_tests": p["run_tests"],
            "plan_file": f"{C.STATE_DIR}/plan-{p['check']}.json".replace("\\", "/"),
            "new_findings_file": p["new_findings_file"], "agent_brief": p["agent_brief"], "prep_commands": p["prep_commands"],
        } for p in plans],
        "preload": {"files": len(union), "tokens": total, "ok": 0 < total <= a.preload_budget, "budget": a.preload_budget},
        "all_skip": all(p["skip"] for p in plans),
    }
    if any(pr["script"] == "osv_check.py" for cid in ids for pr in C.registry_entry(cid).get("prep", [])):
        summary["osv_stale"] = stale
    C.save_json(C.state_path(root, "plan.json"), {**summary, "preload_files": sorted(union)})
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
