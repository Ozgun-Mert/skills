"""Make sure the optimize-seo state folder is gitignored.

Adds `/<state-dir>/` once to the project-root .gitignore (creating it if missing), detects a
collision with an existing app folder of the same name, verifies with `git check-ignore`, and
reports state files that git already tracks. Never runs a git command that changes anything.

Usage: python ensure_gitignore.py --root . [--state-dir seo] [--dry-run]
Prints JSON.
"""
import argparse
import json
import os
import subprocess
import sys

COMMENT = "# optimize-seo state (local only)"
STATE_MARKER = "seo-plan.json"


def git(root, *args):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--state-dir", default="seo")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    name = a.state_dir.strip("/\\")
    line = f"/{name}/"
    state_path = os.path.join(root, name)
    out = {"root": root, "state_dir": name, "line": line, "gitignore_created": False,
           "line_added": False, "already_present": False, "collision": False,
           "is_git_repo": False, "ignored_verified": None, "tracked_files": [], "notes": []}

    # Collision: an existing folder with this name that is not ours.
    if os.path.isdir(state_path) and not os.path.exists(os.path.join(state_path, STATE_MARKER)):
        entries = [e for e in os.listdir(state_path) if not e.startswith(".")]
        ours = {"research", "crawl.json", "sitemap-check.json", "seo-plan.md"}
        foreign = [e for e in entries if e not in ours and not e.startswith("psi-")]
        if foreign:
            out["collision"] = True
            out["collision_entries"] = foreign[:20]
            out["notes"].append(f"'{name}/' already exists and holds non-optimize-seo files. "
                                "Ask the user for another state folder name and re-run with --state-dir.")
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return

    gi = os.path.join(root, ".gitignore")
    existing = ""
    if os.path.exists(gi):
        with open(gi, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
    lines = [l.strip() for l in existing.splitlines()]
    variants = {line, f"{name}/", f"/{name}", name, f"/{name}/*", f"{name}/*"}
    if any(l in variants for l in lines):
        out["already_present"] = True
    elif not a.dry_run:
        out["gitignore_created"] = not os.path.exists(gi)
        block = ("" if not existing or existing.endswith("\n") else "\n")
        block += ("\n" if existing.strip() else "") + f"{COMMENT}\n{line}\n"
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            f.write(block)
        out["line_added"] = True

    code, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if code == 0:
        out["is_git_repo"] = True
        probe = f"{name}/{STATE_MARKER}"
        c, _ = git(root, "check-ignore", "-q", probe)
        out["ignored_verified"] = (c == 0)
        if c != 0:
            out["notes"].append(f"git check-ignore says {probe} is NOT ignored. Check for a negating "
                                "rule (!...) in .gitignore or a parent .gitignore.")
        c, tracked = git(root, "ls-files", "--", f"{name}/")
        if c == 0 and tracked:
            out["tracked_files"] = tracked.splitlines()
            out["notes"].append(f"Files under {name}/ are already tracked. .gitignore won't untrack "
                                f"them. Tell the user to run: git rm -r --cached {name}")
    else:
        out["notes"].append("Not a git repository (or git not installed). .gitignore written anyway.")

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
