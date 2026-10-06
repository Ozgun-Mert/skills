"""Keep every backend-checker output out of git.

Adds docs/SECURITY_PROBLEMS.md, docs/CODE_QUALITY.md and docs/.backend-checks/ (plus the output file
of any other registered check) to the project-root .gitignore once, verifies with `git check-ignore`,
and reports outputs git already tracks. Never runs a git command that changes anything.

Usage: python ensure_gitignore.py --root . [--dry-run]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

COMMENT = "# backend-checker reports (local only: they map your weaknesses)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    wanted = ["/" + C.STATE_DIR.replace("\\", "/") + "/"] + ["/" + c["output_md"] for c in C.load_registry()]
    gi = os.path.join(root, ".gitignore")
    existing = open(gi, encoding="utf-8", errors="replace").read() if os.path.exists(gi) else ""
    have = {l.strip().lstrip("/").rstrip("/") for l in existing.splitlines()}
    missing = [w for w in wanted if w.strip("/") not in have]
    out = {"gitignore": C.rel(gi, root), "added": [], "already_present": [w for w in wanted if w not in missing],
           "tracked": [], "notes": []}
    if missing and not a.dry_run:
        block = ("" if not existing or existing.endswith("\n") else "\n") + ("\n" if existing.strip() else "")
        block += COMMENT + "\n" + "\n".join(missing) + "\n"
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            f.write(block)
        out["added"] = missing
    code, _ = C.git(root, "rev-parse", "--is-inside-work-tree")
    if code == 0:
        for w in wanted:
            probe = w.strip("/") + ("/index.json" if w.endswith("/") else "")
            c, _ = C.git(root, "check-ignore", "-q", probe)
            if c != 0:
                out["notes"].append(f"{probe} is NOT ignored: look for a negating rule (!...) in .gitignore.")
            c, tracked = C.git(root, "ls-files", "--", w.strip("/"))
            if c == 0 and tracked.strip():
                out["tracked"] += tracked.strip().splitlines()
        if out["tracked"]:
            out["notes"].append("Already tracked by git, so .gitignore does not hide them. Tell the user to run: git rm --cached "
                                + " ".join(f'"{t}"' for t in out["tracked"][:5]) + " (the skill never runs it).")
    else:
        out["notes"].append("Not a git repository; .gitignore written anyway.")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
