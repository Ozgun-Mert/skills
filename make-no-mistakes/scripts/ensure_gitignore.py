"""Make sure the make-no-mistakes working folder and env files are gitignored.

Adds, once, under a marker comment in the project-root .gitignore (created if missing):
    /mnm/
    .env
    .env.*
    !.env.example
Verifies with `git check-ignore` when the folder is a git repo and reports files git already
tracks. Never runs a git command that changes anything.

Usage: python ensure_gitignore.py --root . [--dry-run]
Prints JSON.
"""
import argparse
import json
import os
import subprocess
import sys

COMMENT = "# make-no-mistakes (local only)"
WANTED = ["/mnm/", ".env", ".env.*", "!.env.example"]
EQUIVALENT = {
    "/mnm/": {"/mnm/", "mnm/", "/mnm", "mnm", "/mnm/*", "mnm/*"},
    ".env": {".env", "/.env", "*.env"},
    ".env.*": {".env.*", "/.env.*", ".env*", "/.env*"},
    "!.env.example": {"!.env.example", "!/.env.example"},
}


def git(root, *args):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    gi = os.path.join(root, ".gitignore")
    out = {"root": root, "gitignore_created": False, "lines_added": [], "already_present": [],
           "is_git_repo": False, "ignored_verified": None, "tracked_files": [], "notes": []}

    existing = ""
    if os.path.exists(gi):
        with open(gi, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
    lines = {l.strip() for l in existing.splitlines()}
    missing = []
    for w in WANTED:
        (out["already_present"] if lines & EQUIVALENT[w] else missing).append(w)
    if missing and not a.dry_run:
        out["gitignore_created"] = not os.path.exists(gi)
        block = "" if not existing or existing.endswith("\n") else "\n"
        block += ("\n" if existing.strip() else "") + COMMENT + "\n" + "\n".join(missing) + "\n"
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            f.write(block)
        out["lines_added"] = missing

    code, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if code == 0:
        out["is_git_repo"] = True
        c, _ = git(root, "check-ignore", "-q", "mnm/state.json")
        out["ignored_verified"] = c == 0
        if c != 0:
            out["notes"].append("git check-ignore says mnm/state.json is NOT ignored; look for a "
                                "negating rule (!...) in .gitignore or a parent .gitignore.")
        c, tracked = git(root, "ls-files", "--", "mnm/", ".env")
        if c == 0 and tracked:
            out["tracked_files"] = tracked.splitlines()
            out["notes"].append("These files are already tracked; .gitignore won't untrack them. "
                                "Tell the user to run: git rm -r --cached " + " ".join(sorted(
                                    {p.split('/')[0] for p in out["tracked_files"]})))
    else:
        out["notes"].append("Not a git repository (or git not installed). .gitignore written anyway.")

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
