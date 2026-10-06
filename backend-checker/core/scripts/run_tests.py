"""Run the project's existing test command (section 3). No installs, no docker, hard time cap.

Start it in the background, keep analyzing, then call it again with --wait to collect the result:
  python run_tests.py --root .            # runs the detected command, writes tests.json + tests.log
  python run_tests.py --root . --wait     # blocks until tests.json says finished (or the cap passes)

CI=true is set so watch-mode runners (vitest/jest) exit after one run. Output is masked for secrets.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

FAIL_LINE = re.compile(r"(?i)(\bfail(ed|ing|ure)?\b|\berror\b|✗|✕|×|not ok|assert|expected|received|traceback|exception|panic:|--- FAIL)")


def summarize(path_log, result):
    try:
        lines = open(path_log, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        lines = []
    result["failure_lines"] = [C.mask_text(l[:240]) for l in lines if FAIL_LINE.search(l)][:80]
    result["tail"] = [C.mask_text(l[:240]) for l in lines[-60:]]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--cmd", help="override the detected test command")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out_json = C.state_path(root, "tests.json")
    out_log = C.state_path(root, "tests.log")

    if a.wait:
        deadline = time.time() + a.timeout + 30
        while time.time() < deadline:
            r = C.load_json(out_json)
            if r and r.get("status") != "running":
                print(json.dumps({k: v for k, v in r.items() if k != "tail"}, ensure_ascii=False, indent=1))
                return 0
            time.sleep(3)
        print(json.dumps({"status": "unknown", "note": "tests.json never finished; treat as 'Could not run: timed out'"}))
        return 1

    index = C.load_json(C.state_path(root, "index.json"), {})
    t = index.get("tests") or {}
    cmd = a.cmd or t.get("command")
    if not cmd:
        r = {"status": "no_suite", "note": "No test suite detected.", "test_files": t.get("test_files", 0)}
        C.save_json(out_json, r)
        print(json.dumps(r))
        return 0
    cwd = os.path.join(root, t.get("cwd") or ".")
    # Missing dependencies don't stop the attempt: node --test, go test or pytest on plain code may need nothing
    # installed. If it fails for that reason, the agent reports "Could not run: missing X".
    C.save_json(out_json, {"status": "running", "command": cmd, "cwd": t.get("cwd"), "started_at": C.now_iso()})
    env = dict(os.environ, CI="true", FORCE_COLOR="0", NO_COLOR="1")
    start = time.time()
    status, code = "finished", None
    with open(out_log, "w", encoding="utf-8", errors="replace") as log:
        try:
            p = subprocess.run(cmd, shell=True, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=a.timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            status = "timed_out"
        except OSError as e:
            status = "error"
            log.write(str(e))
    r = {"status": status, "command": cmd, "cwd": t.get("cwd"), "exit_code": code, "passed": code == 0 if status == "finished" else None,
         "duration_s": round(time.time() - start, 1), "deps_installed": t.get("deps_installed"), "log": C.rel(out_log, root)}
    summarize(out_log, r)
    C.save_json(out_json, r)
    print(json.dumps({k: v for k, v in r.items() if k != "tail"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
