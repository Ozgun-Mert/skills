"""Validate mnm/prompts/*.md before launching workers, or check one piece's file ownership.

Validate (default):
  - front matter with `piece`, `ownership`, optional `depends_on`, `max_turns`
  - all required sections present, in order
  - goal condition present, <= 4000 chars, names the report and the ownership check
  - piece names unique, dependencies exist, no cycles
  - overlapping ownership only between pieces linked by a dependency path
  Prints errors/warnings and the wave table; stores `waves` in mnm/state.json.

Ownership check (used by workers and the orchestrator):
  python validate_prompts.py --root . --check-ownership <piece>
  Lists files changed since the piece started that match neither its ownership nor the
  ownership of a piece running at the same time. Prints "ownership: clean" or the violations.

Usage: python validate_prompts.py --root . [--check-ownership PIECE] [--json]
Exit code 1 on errors/violations.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

MAX_COND = 4000
WARN_COND = 2500


def compute_waves(deps):
    """Topological levels. Returns (waves, cycle_nodes)."""
    level, remaining = {}, dict(deps)
    waves = []
    while remaining:
        ready = sorted(p for p, ds in remaining.items() if all(d in level for d in ds))
        if not ready:
            return waves, sorted(remaining)
        for p in ready:
            level[p] = len(waves)
        waves.append(ready)
        for p in ready:
            remaining.pop(p)
    return waves, []


def ancestors(piece, deps, seen=None):
    seen = set() if seen is None else seen
    for d in deps.get(piece, []):
        if d not in seen and d in deps:
            seen.add(d)
            ancestors(d, deps, seen)
    return seen


def validate(root, as_json):
    prompts = C.load_prompts(root)
    errors, warnings = [], []
    if not prompts:
        errors.append("no prompt files in mnm/prompts/")
    deps, owns = {}, {}
    for piece, entries in prompts.items():
        if len(entries) > 1:
            errors.append(f"piece '{piece}' is defined in several files: {[e['file'] for e in entries]}")
        e = entries[0]
        f = e["file"]
        if e["meta"] is None:
            errors.append(f"{f}: missing front matter (--- piece/depends_on/max_turns/ownership ---)")
            continue
        own = C.ownership(e["meta"])
        if not own:
            errors.append(f"{f}: front matter has no ownership globs")
        deps[piece] = C.depends(e["meta"])
        owns[piece] = own
        missing = [s for s in C.SECTIONS if s not in e["sections"]]
        if missing:
            errors.append(f"{f}: missing sections {missing}")
        else:
            idx = [e["order"].index(s) for s in C.SECTIONS]
            if idx != sorted(idx):
                warnings.append(f"{f}: sections are not in the standard order {C.SECTIONS}")
        cond = e["condition"]
        if not cond:
            errors.append(f"{f}: '## Goal condition' needs one ```text fenced block")
        else:
            n = len(cond)
            if n > MAX_COND:
                errors.append(f"{f}: goal condition is {n} chars (max {MAX_COND}); move detail into the prompt body")
            elif n > WARN_COND:
                warnings.append(f"{f}: goal condition is {n} chars; aim for ~1500")
            if f"mnm/reports/{piece}" not in cond:
                errors.append(f"{f}: goal condition must require mnm/reports/{piece}.md")
            if "--check-ownership" not in cond:
                errors.append(f"{f}: goal condition must include the --check-ownership {piece} command")
            if "turn" not in cond.lower():
                warnings.append(f"{f}: goal condition has no turn cap ('or stop after N turns')")
            if "<SKILL_DIR>" in cond:
                warnings.append(f"{f}: <SKILL_DIR> placeholder left in the condition (launch_worker.py "
                                "substitutes it, but prefer the real path)")
            if "mnm/prompts/" not in cond:
                warnings.append(f"{f}: goal condition should tell the worker to read its prompt file first")
        if "Acceptance" in e["sections"] and "A1" not in e["sections"]["Acceptance"]:
            warnings.append(f"{f}: acceptance criteria should be numbered A1…An")
        mt = e["meta"].get("max_turns")
        if mt and not str(mt).isdigit():
            errors.append(f"{f}: max_turns must be an integer")

    for p, ds in deps.items():
        for d in ds:
            if d not in deps:
                errors.append(f"piece '{p}' depends on unknown piece '{d}'")
    clean_deps = {p: [d for d in ds if d in deps] for p, ds in deps.items()}
    waves, cycle = compute_waves(clean_deps)
    if cycle:
        errors.append(f"dependency cycle among: {cycle}")

    names = sorted(owns)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a in ancestors(b, clean_deps) or b in ancestors(a, clean_deps):
                continue
            clash = [(x, y) for x in owns[a] for y in owns[b] if C.globs_overlap(x, y)]
            if clash:
                errors.append(f"ownership overlap between '{a}' and '{b}' (they can run at the same "
                              f"time): {clash[:3]}. Narrow the globs or add a dependency.")

    if not errors:
        def fn(st):
            st["waves"] = waves
            pcs = st.setdefault("pieces", {})
            for p, entries in prompts.items():
                pcs.setdefault(p, {"status": "pending"})["file"] = entries[0]["file"]
        C.update_state(root, fn)

    if as_json:
        print(json.dumps({"errors": errors, "warnings": warnings, "waves": waves}, indent=1))
    else:
        for e in errors:
            print("ERROR  " + e)
        for w in warnings:
            print("WARN   " + w)
        if waves and not cycle:
            print("\n| Wave | Pieces (run in parallel) |\n|---|---|")
            for i, w in enumerate(waves):
                print(f"| W{i} | {', '.join(w)} |")
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def check_ownership(root, piece, as_json):
    prompts = C.load_prompts(root)
    if piece not in prompts:
        print(f"unknown piece '{piece}'")
        return 1
    st = C.load_state(root)
    pinfo = st.get("pieces", {}).get(piece, {})
    started = pinfo.get("started_at")
    if not started:
        print("ownership: unknown (piece has no started_at in mnm/state.json; launch it with launch_worker.py)")
        return 1
    own = C.ownership(prompts[piece][0]["meta"])
    concurrent = []
    for other, info in st.get("pieces", {}).items():
        if other == piece or other not in prompts:
            continue
        # A piece that ran during any part of this piece's run may own some of the changes.
        o_start, o_end = info.get("started_at"), info.get("ended_at")
        if o_start and (info.get("status") == "running" or (o_end and o_end >= started)):
            concurrent.append(other)
    other_globs = [g for o in concurrent for g in C.ownership(prompts[o][0]["meta"])]
    changed = C.changed_since(root, started)
    violations = [p for p in changed if not C.matches(p, own) and not C.matches(p, other_globs)]
    result = {"piece": piece, "changed": len(changed), "concurrent": concurrent, "violations": violations}
    if as_json:
        print(json.dumps(result, indent=1))
    elif violations:
        print(f"ownership: {len(violations)} violation(s) for '{piece}' (files outside {own}):")
        for v in violations[:50]:
            print("  " + v)
        print("Revert these changes, or ask the orchestrator through a question if they are needed.")
    else:
        print(f"ownership: clean ({len(changed)} changed file(s) checked for '{piece}')")
    return 1 if violations else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--check-ownership", metavar="PIECE")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if a.check_ownership:
        return check_ownership(root, a.check_ownership, a.json)
    return validate(root, a.json)


if __name__ == "__main__":
    sys.exit(main())
