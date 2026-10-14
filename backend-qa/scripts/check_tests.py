"""Check that the test writer's work is complete and stayed inside its lane. Prints READY or NOT READY.

READY needs all of:
  1. qa/test-commands.json exists with test_command and junit_command.
  2. qa/results/results.json exists, is newer than every new/changed test file, and has
     harness_errors=0 (every test file loads; DB/setup works).
  3. Every active decision ID in qa/TEST_DECISIONS.md appears in at least one test that ran,
     or is listed in qa/untestable.json with a reason.
  4. No application file changed (git status, read-only): only tests, test helpers/config,
     manifests/lockfiles, .env.test.example, .gitignore and qa/ may change. Files that were
     already dirty before the worker started (baseline in qa/state.json) are ignored if unchanged.
  5. package.json / composer.json: only scripts and dev dependencies changed vs HEAD, no script
     removed.

Usage: python check_tests.py --root .
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ALLOWED = re.compile(
    r"^qa/|(^|/)\.gitignore$|(^|/)\.env\.test\.example$|"
    r"(^|/)(package\.json|package-lock\.json|bun\.lockb?|pnpm-lock\.yaml|yarn\.lock|deno\.json|deno\.lock|"
    r"pyproject\.toml|uv\.lock|poetry\.lock|pdm\.lock|requirements[-_](dev|test)[\w-]*\.txt|"
    r"go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|composer\.json|composer\.lock|Gemfile|Gemfile\.lock|"
    r"pom\.xml|build\.gradle(\.kts)?|Makefile|"
    r"bunfig\.toml|vitest\.config\.\w+|vitest\.workspace\.\w+|jest\.config\.\w+|jest\.setup\.\w+|\.mocharc\.\w+|"
    r"pytest\.ini|setup\.cfg|tox\.ini|conftest\.py|phpunit\.xml(\.dist)?|\.rspec|tsconfig\.test\.json|"
    r"docker-compose\.test\.ya?ml|compose\.test\.ya?ml|\.config/nextest\.toml)$")
WARN_ONLY = re.compile(r"(^|/)(pyproject\.toml|Makefile|pom\.xml|build\.gradle(\.kts)?|Cargo\.toml|Gemfile|go\.mod|setup\.cfg)$")


def git_dirty(root):
    code, out = C.git(root, "status", "--porcelain=v1", "-uall")
    if code != 0:
        return None
    files = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip().strip('"'))
    return files


def file_sha(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as f:
            import hashlib
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return "(missing)"


def manifest_issues(root, rel):
    """Changes outside scripts/dev deps in package.json / composer.json vs HEAD."""
    code, head = C.git(root, "show", f"HEAD:{rel}")
    if code != 0 or not head.strip():
        return []
    try:
        old = json.loads(head)
        new = C.load_json(os.path.join(root, rel))
    except ValueError:
        return [f"{rel}: could not parse to compare"]
    if not isinstance(new, dict):
        return [f"{rel}: not valid JSON now"]
    issues = []
    free = {"package.json": {"scripts", "devDependencies", "jest", "jest-junit", "vitest", "c8", "nyc", "mocha"},
            "composer.json": {"scripts", "require-dev", "autoload-dev", "scripts-descriptions"}}[os.path.basename(rel)]
    for k in sorted(set(old) | set(new)):
        if k in free:
            continue
        if old.get(k) != new.get(k):
            issues.append(f"{rel}: `{k}` changed (only test scripts and dev dependencies may change)")
    gone = sorted(set((old.get("scripts") or {})) - set((new.get("scripts") or {})))
    if gone:
        issues.append(f"{rel}: scripts removed: {', '.join(gone)} (never remove the user's scripts)")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    problems, warnings, info = [], [], []

    # 1. commands
    cmds = C.load_json(C.qa_path(root, "test-commands.json"))
    if not cmds or not cmds.get("test_command") or not cmds.get("junit_command"):
        problems.append("qa/test-commands.json missing or lacks test_command/junit_command")
    else:
        info.append(f"full-suite command: {cmds['test_command']}")

    # 2. results
    res_path = C.qa_path(root, "results", "results.json")
    res = C.load_json(res_path)
    dirty = git_dirty(root)
    if not res:
        problems.append("qa/results/results.json missing: run run_tests.py")
    else:
        s = res.get("summary", {})
        info.append("suite: " + " ".join(f"{k}={v}" for k, v in s.items()))
        if s.get("harness_errors"):
            names = [t["key"] for t in res.get("tests", []) if t.get("harness")][:10]
            problems.append(f"harness_errors={s['harness_errors']} (tests that don't load or setup failures): " + "; ".join(names))
        if not s.get("total"):
            problems.append("the suite reported 0 tests")
        rtime = os.path.getmtime(res_path)
        newer = []
        for f in dirty or []:
            if C.TEST_PATH.search(f) and os.path.exists(os.path.join(root, f)) and os.path.getmtime(os.path.join(root, f)) > rtime + 1:
                newer.append(f)
        if newer:
            problems.append("results are stale; test files changed after the last run: " + ", ".join(newer[:8]))

    # 3. decision coverage
    dec = C.load_decisions(root)
    active = set(dec["active"])
    ran = set()
    for t in (res or {}).get("tests", []):
        ran.update(t.get("decisions") or [])
    unt = C.load_json(C.qa_path(root, "untestable.json"), []) or []
    unt_ids = {u.get("id") for u in unt if isinstance(u, dict) and u.get("reason")}
    missing = sorted(active - ran - unt_ids, key=lambda x: (x[0], x))
    if missing:
        problems.append(f"{len(missing)} active decision(s) have no test that ran: " + ", ".join(missing[:40]) +
                        (" …" if len(missing) > 40 else ""))
    info.append(f"decisions: {len(active)} active · {len(active & ran)} tested · {len(active & unt_ids)} untestable")
    stale_retired = sorted(dec["retired"] & ran)
    if stale_retired:
        warnings.append("tests still cite retired decisions: " + ", ".join(stale_retired[:20]))
    unknown = sorted(ran - active - dec["retired"])
    if unknown:
        warnings.append("tests cite IDs not in TEST_DECISIONS.md: " + ", ".join(unknown[:20]))

    # 4/5. lane check
    if dirty is None:
        warnings.append("not a git repository: can't verify that application code is untouched")
    else:
        base = (C.load_state(root).get("worker") or {}).get("baseline_dirty") or {}
        touched = []
        for f in dirty:
            if ALLOWED.search(f) or C.TEST_PATH.search(f):
                if WARN_ONLY.search(f) and not (f in base and base[f] == file_sha(root, f)):
                    warnings.append(f"{f} changed: confirm only test/dev sections were edited")
                continue
            if f in base and base[f] == file_sha(root, f):
                continue  # dirty before the worker started, unchanged since
            touched.append(f)
        if touched:
            problems.append("application files changed (must be reverted): " + ", ".join(touched[:15]))
        else:
            info.append("app code: untouched")
        for f in dirty:
            if os.path.basename(f) in ("package.json", "composer.json") and not (f in base and base[f] == file_sha(root, f)):
                problems.extend(manifest_issues(root, f))

    for line in info:
        print(line)
    for w in warnings:
        print("warning: " + w)
    for p in problems:
        print("problem: " + p)
    print("READY" if not problems else f"NOT READY ({len(problems)} problem(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
