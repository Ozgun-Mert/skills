"""Run the full test suite (or one file) and turn the JUnit output into qa/results/results.json.

Reads qa/test-commands.json (written by the worker):
  test_command, junit_command, junit_paths, coverage_command, coverage_paths, file_command, cwd
Runs junit_command (same tests as the user's test_command) with CI=true and a time cap, parses
every JUnit XML file, maps each test to its function (`F012 …` describe/class) and decision IDs
(`[F012-D3]` in the title), flags harness errors (test files that don't load, DB/setup failures),
and optionally parses coverage (lcov, Cobertura, JaCoCo, Go cover profile) per function.

Usage:
  python run_tests.py --root .                    # full suite → results.json + SUMMARY line
  python run_tests.py --root . --coverage         # also run coverage_command and map it to functions
  python run_tests.py --root . --file tests/qa/orders.test.ts --times 2   # flake check
  python run_tests.py --root . --parse-only       # re-parse existing JUnit files
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HARNESS = re.compile(
    r"(?i)cannot find module|module not found|modulenotfounderror|importerror|syntaxerror|unexpected token|"
    r"transform failed|failed to load|error while loading|collection|no tests? (?:found|ran)|"
    r"econnrefused|connection refused|could not connect|connect etimedout|getaddrinfo|"
    r"database .* does not exist|role .* does not exist|password authentication failed|"
    r"fixture '.*' not found|error in (?:before|after)(?:all|each)|beforeall|afterall|hook failed|"
    r"is not defined in the environment|missing (?:required )?env|environment variable .* (?:is )?(?:not set|missing)|"
    r"docker|testcontainers|container .* (?:failed|exited)|compilation (?:error|failed)|cannot compile|build failed|"
    r"undefined: |no required module provides package|cannot use .* as|error ts\d{3,}")
FAIL_LINE = re.compile(r"(?i)(\bfail(ed|ing|ure)?\b|\berror\b|✗|✕|×|not ok|assert|expected|received|traceback|panic:|--- FAIL)")


def load_commands(root):
    cmds = C.load_json(C.qa_path(root, "test-commands.json"))
    if not cmds or not cmds.get("junit_command"):
        raise SystemExit("qa/test-commands.json missing or has no junit_command (the worker writes it; see test-setup.md)")
    cmds.setdefault("junit_paths", ["qa/results/junit.xml"])
    cmds.setdefault("cwd", ".")
    return cmds


def run_cmd(cmd, cwd, log_path, timeout):
    env = dict(os.environ, CI="true", FORCE_COLOR="0", NO_COLOR="1", NODE_ENV=os.environ.get("NODE_ENV", "test"))
    start = time.time()
    status, code = "finished", None
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        try:
            p = subprocess.run(cmd, shell=True, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            status = "timed_out"
        except OSError as e:
            status = "error"
            log.write(str(e))
    return {"status": status, "exit_code": code, "duration_s": round(time.time() - start, 1)}


def expand(root, cwd, patterns):
    files = []
    for pat in patterns:
        for base in dict.fromkeys([root, os.path.join(root, cwd)]):
            files.extend(glob.glob(os.path.join(base, pat), recursive=True))
    return sorted(set(os.path.abspath(f) for f in files))


def text_of(el):
    if el is None:
        return ""
    msg = el.get("message") or ""
    body = (el.text or "").strip()
    return (msg + ("\n" + body if body and body not in msg else "")).strip()


def parse_junit(root, paths):
    tests = []
    for path in paths:
        try:
            tree = ET.parse(path)
        except (ET.ParseError, OSError) as e:
            tests.append({"key": f"(unparsable) {C.rel(path, root)}", "name": "JUnit file could not be parsed", "suite": "",
                          "file": None, "status": "error", "message": str(e)[:300], "harness": True})
            continue
        for suite in tree.getroot().iter("testsuite"):
            sfile = suite.get("file") or suite.get("filepath")
            # suite-level errors (a file that failed to load) without testcases
            cases = list(suite.findall("testcase"))
            if not cases and int(suite.get("errors", "0") or 0) + int(suite.get("failures", "0") or 0) > 0:
                msg = text_of(suite.find("system-err")) or text_of(suite.find("error")) or "suite failed without test cases"
                tests.append({"key": f"{sfile or suite.get('name')}::(suite)", "name": "(suite failed to run)",
                              "suite": suite.get("name") or "", "file": sfile, "status": "error",
                              "message": C.mask_text(msg[:1500]), "harness": True})
            for tc in cases:
                name = tc.get("name") or ""
                cls = tc.get("classname") or suite.get("name") or ""
                f = tc.get("file") or sfile
                if not f and re.search(r"[/\\].+\.\w+$", cls):
                    f = cls
                fail, err, skip = tc.find("failure"), tc.find("error"), tc.find("skipped")
                status = "failed" if fail is not None else "error" if err is not None else "skipped" if skip is not None else "passed"
                msg = text_of(fail if fail is not None else err)
                tests.append({"key": f"{f or cls}::{cls}::{name}" if f and f != cls else f"{cls}::{name}",
                              "name": name, "suite": cls, "file": f, "line": tc.get("line"),
                              "status": status, "time": tc.get("time"),
                              "message": C.mask_text(msg[:1500]) if msg else "",
                              "harness": bool(status in ("failed", "error") and HARNESS.search(msg or "")
                                              and not re.search(r"(?i)expected|assert|toBe|toEqual|received", (msg or "")[:300]))})
    for t in tests:
        f = (t.get("file") or "").replace("\\", "/")
        if f and os.path.isabs(f):
            f = C.rel(f, root)
        t["file"] = f or None
        hay = f"{t['suite']} {t['name']}"
        t["decisions"] = sorted(set(C.ID_IN_TEXT.findall(hay)))
        fm = C.FUNC_ID_IN_TEXT.findall(hay)
        t["function"] = fm[0] if fm else (t["decisions"][0].split("-D")[0] if t["decisions"] and t["decisions"][0].startswith("F") else None)
    return tests


# ----------------------------------------------------------------------------- coverage

def parse_coverage(root, cwd, paths):
    """{relpath: {"hit": set(lines), "found": set(lines)}} from lcov / Cobertura / JaCoCo / Go profiles."""
    cov = {}

    def add(f, line, hits):
        f = f.replace("\\", "/")
        for base in (root, os.path.join(root, cwd)):
            cand = f if os.path.isabs(f) else os.path.join(base, f)
            if os.path.exists(cand):
                f = C.rel(cand, root)
                break
        e = cov.setdefault(f, {"hit": set(), "found": set()})
        e["found"].add(int(line))
        if int(hits) > 0:
            e["hit"].add(int(line))

    for path in paths:
        text = C.read_text(path, limit=200_000_000) or ""
        if path.endswith(".info") or text.startswith("TN:") or "\nSF:" in text[:2000] or text.startswith("SF:"):
            cur = None
            for line in text.splitlines():
                if line.startswith("SF:"):
                    cur = line[3:].strip()
                elif line.startswith("DA:") and cur:
                    parts = line[3:].split(",")
                    if len(parts) >= 2 and parts[0].isdigit():
                        add(cur, parts[0], parts[1] if parts[1].lstrip("-").isdigit() else 0)
        elif text.startswith("mode:"):  # go cover profile: file:sl.sc,el.ec stmts count
            for line in text.splitlines()[1:]:
                m = re.match(r"^(.+):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$", line)
                if m:
                    f = m.group(1)
                    mod = (C.read_text(os.path.join(root, "go.mod")) or "")
                    mm = re.search(r"^module\s+(\S+)", mod, re.M)
                    if mm and f.startswith(mm.group(1) + "/"):
                        f = f[len(mm.group(1)) + 1:]
                    for ln in range(int(m.group(2)), int(m.group(3)) + 1):
                        add(f, ln, m.group(4))
        elif "<" in text[:200]:
            try:
                rootel = ET.fromstring(text)
            except ET.ParseError:
                continue
            if rootel.tag == "coverage":  # Cobertura
                sources = [s.text.strip() for s in rootel.iter("source") if s.text]
                for cls in rootel.iter("class"):
                    fn = cls.get("filename") or ""
                    full = next((os.path.join(s, fn) for s in sources if os.path.exists(os.path.join(s, fn))), fn)
                    for ln in cls.iter("line"):
                        add(full, ln.get("number", 0), ln.get("hits", 0))
            elif rootel.tag == "report":  # JaCoCo
                for pkg in rootel.iter("package"):
                    for sf in pkg.iter("sourcefile"):
                        fn = f"{pkg.get('name', '')}/{sf.get('name', '')}"
                        hits = [os.path.join(dp, f) for dp, _d, fs in os.walk(root) for f in fs
                                if os.path.join(dp, f).replace("\\", "/").endswith(fn)] if fn else []
                        target = hits[0] if hits else fn
                        for ln in sf.iter("line"):
                            add(target, ln.get("nr", 0), ln.get("ci", 0))
    return cov


def function_coverage(fmap, cov):
    out = {}
    for f in fmap.get("functions", []):
        e = cov.get(f["file"])
        if not e:
            continue
        rng = set(range(f["start"], f["end"] + 1))
        found = e["found"] & rng
        if not found:
            continue
        out[f["id"]] = round(100.0 * len(e["hit"] & rng) / len(found), 1)
    return out


# ----------------------------------------------------------------------------- main

def summarize(tests, fmap):
    s = {"total": len(tests), "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "harness_errors": 0}
    for t in tests:
        s[{"passed": "passed", "failed": "failed", "error": "errors", "skipped": "skipped"}[t["status"]]] += 1
        if t.get("harness"):
            s["harness_errors"] += 1
    names = {f["id"]: f for f in fmap.get("functions", [])}
    per = {}
    for t in tests:
        fid = t.get("function") or "(existing tests)"
        e = per.setdefault(fid, {"passed": 0, "failed": 0, "errors": 0, "skipped": 0})
        e[{"passed": "passed", "failed": "failed", "error": "errors", "skipped": "skipped"}[t["status"]]] += 1
    for fid, e in per.items():
        f = names.get(fid)
        if f:
            e.update(name=f["name"], file=f["file"], start=f["start"],
                     route=f"{f['route']['method']} {f['route']['path']}" if f.get("route") else None)
    s["functions_failing"] = sum(1 for k, e in per.items() if k.startswith("F") and (e["failed"] or e["errors"]))
    s["functions_tested"] = sum(1 for k in per if k.startswith("F"))
    return s, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--file", help="run only this test file via file_command (flake check)")
    ap.add_argument("--times", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--parse-only", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    cmds = load_commands(root)
    cwd = os.path.join(root, cmds["cwd"])
    rdir = C.qa_path(root, "results")
    os.makedirs(rdir, exist_ok=True)
    fmap = C.load_json(C.qa_path(root, "function-map.json"), {}) or {}

    if a.file:
        if not cmds.get("file_command"):
            raise SystemExit("qa/test-commands.json has no file_command")
        runs = []
        for i in range(max(1, a.times)):
            log = os.path.join(rdir, f"rerun-{i + 1}.log")
            r = run_cmd(cmds["file_command"].replace("{file}", a.file), cwd, log, a.timeout)
            r["passed"] = r["exit_code"] == 0
            r["log"] = C.rel(log, root)
            runs.append(r)
        print(json.dumps({"file": a.file, "runs": runs, "passed_any": any(r["passed"] for r in runs)}, indent=1))
        print("RERUN " + " ".join(("pass" if r["passed"] else "fail") for r in runs))
        return 0

    run_info = {"status": "parsed_only"}
    if not a.parse_only:
        for old in expand(root, cmds["cwd"], cmds["junit_paths"]):
            try:
                os.remove(old)  # stale results must not be read as this run's
            except OSError:
                pass
        run_info = run_cmd(cmds["junit_command"], cwd, os.path.join(rdir, "junit-run.log"), a.timeout)
    paths = expand(root, cmds["cwd"], cmds["junit_paths"])
    tests = parse_junit(root, paths)
    if not tests and run_info.get("status") != "parsed_only":
        log = C.read_text(os.path.join(rdir, "junit-run.log")) or ""
        fails = [C.mask_text(l[:240]) for l in log.splitlines() if FAIL_LINE.search(l)][:40]
        tests = [{"key": "(no results)", "name": "suite produced no JUnit results", "suite": "", "file": None,
                  "status": "error", "message": "\n".join(fails or log.splitlines()[-30:])[:3000], "harness": True,
                  "decisions": [], "function": None}]
    summary, per = summarize(tests, fmap)

    coverage = None
    if a.coverage and cmds.get("coverage_command"):
        cinfo = run_cmd(cmds["coverage_command"], cwd, os.path.join(rdir, "coverage-run.log"), a.timeout)
        cov = parse_coverage(root, cmds["cwd"], expand(root, cmds["cwd"], cmds.get("coverage_paths") or []))
        coverage = {"run": cinfo, "files": len(cov), "functions": function_coverage(fmap, cov)}
    elif a.coverage:
        coverage = {"run": {"status": "no coverage_command"}, "functions": {}}

    res = {"generated_at": C.now_iso(), "command": cmds.get("test_command"), "junit_command": cmds["junit_command"],
           "run": run_info, "junit_files": [C.rel(p, root) for p in paths], "summary": summary,
           "per_function": per, "tests": tests, "coverage": coverage}
    C.save_json(os.path.join(rdir, "results.json"), res)
    print("SUMMARY " + " ".join(f"{k}={v}" for k, v in summary.items()))
    for t in tests:
        if t["status"] in ("failed", "error"):
            print(f"  {'HARNESS' if t.get('harness') else t['status'].upper():<7} {t['key']}")
    if coverage is not None:
        print(f"coverage: {coverage['run'].get('status')} · functions with data: {len(coverage['functions'])}")
    print("written: qa/results/results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
