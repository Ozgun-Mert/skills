"""Run the qa-backend test writer as one headless /goal worker and record the outcome.

Builds:  claude -p "/goal <condition>" --output-format stream-json --verbose
                --permission-mode <mode> --permission-prompts none
                --append-system-prompt <references/worker-contract.md>
                [--resume <session_id>] [--allowedTools ...] [--model ...] [--max-budget-usd ...]
The condition comes from the "## Goal condition" block of qa/goal-prompt.md. Output streams to
qa/logs/worker.jsonl; session_id, status, turns and cost go to qa/state.json → "worker".

Run it with Bash `run_in_background: true`. It blocks until the worker exits, then prints one
summary line, so the background notification says how it went.

--resume continues the last worker session (it keeps everything it already read). With
--message, the text is saved to qa/answers/ and appended to the goal condition as a FIX-UP, so
the evaluator only accepts the goal once it is done.

Usage:
  python launch_worker.py --root . --check                      # validate qa/goal-prompt.md
  python launch_worker.py --root . --mode auto --skill-dir <SKILL_DIR>
  python launch_worker.py --root . --resume --message "Fix these test bugs: ..."
  python launch_worker.py ... --dry-run                         # print the command only
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

SECTIONS = ["Goal condition", "Context pack", "Layout and naming", "Setup", "Work list", "Constraints", "Report"]
MAX_CONDITION = 4000
TARGET_CONDITION = 1800
TEST_ALLOW = [  # --mode acceptEdits: package managers, runners and read-only helpers only
    "Bash(npm *)", "Bash(npx *)", "Bash(bun *)", "Bash(bunx *)", "Bash(pnpm *)", "Bash(yarn *)", "Bash(node *)",
    "Bash(deno *)", "Bash(uv *)", "Bash(poetry *)", "Bash(pdm *)", "Bash(pip *)", "Bash(python *)", "Bash(python3 *)",
    "Bash(pytest *)", "Bash(go *)", "Bash(gotestsum *)", "Bash(mvn *)", "Bash(./mvnw *)", "Bash(./gradlew *)",
    "Bash(gradle *)", "Bash(dotnet *)", "Bash(composer *)", "Bash(php *)", "Bash(vendor/bin/*)", "Bash(bundle *)",
    "Bash(rake *)", "Bash(rspec *)", "Bash(cargo *)", "Bash(docker compose *)", "Bash(docker-compose *)",
    "Bash(docker ps *)", "Bash(docker info *)", "Bash(make *)", "Bash(cat *)", "Bash(ls *)", "Bash(mkdir *)",
    "Bash(git status *)", "Bash(git diff *)", "Read", "Edit", "Write", "Glob", "Grep",
]


def load_prompt(root):
    path = C.qa_path(root, "goal-prompt.md")
    text = C.read_text(path)
    if text is None:
        raise SystemExit("qa/goal-prompt.md not found; write it first (templates/goal-prompt.md)")
    meta = {}
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*\n", text, re.S)
    body = text
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"^\s*([\w-]+)\s*:\s*(.*)$", line)
            if kv:
                meta[kv.group(1)] = kv.group(2).strip().strip("'\"")
        body = text[m.end():]
    secs, order, cur, fence = {}, [], None, False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fence = not fence
        h = None if fence else re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            cur = h.group(1).strip()
            secs[cur] = ""
            order.append(cur)
        elif cur is not None:
            secs[cur] += line
    cm = re.search(r"```(?:text)?\s*\n(.*?)\n```", secs.get("Goal condition", ""), re.S)
    return {"meta": meta, "sections": secs, "order": order, "condition": cm.group(1).strip() if cm else None, "text": text}


def check(root, p):
    errors, warnings = [], []
    for s in SECTIONS:
        if s not in p["sections"]:
            errors.append(f"missing section: ## {s}")
    cond = p["condition"]
    if not cond:
        errors.append("## Goal condition has no ```text fenced block")
    else:
        if len(cond) > MAX_CONDITION:
            errors.append(f"goal condition is {len(cond)} chars (max {MAX_CONDITION})")
        elif len(cond) > TARGET_CONDITION:
            warnings.append(f"goal condition is {len(cond)} chars; aim for ~1,500")
        for needle, what in (("run_tests.py", "run_tests.py proof"), ("check_tests.py", "check_tests.py READY proof"),
                             ("worker-report.md", "the report + cat"), ("turns", "a turn cap")):
            if needle not in cond:
                errors.append(f"goal condition lacks {what}")
        if re.search(r"<(TEST_COMMAND|SKILL_DIR|N)>", cond):
            errors.append("goal condition still has a <PLACEHOLDER> (TEST_COMMAND / SKILL_DIR / N)")
        for path in re.findall(r'python "([^"]+/scripts/\w+\.py)"', cond):
            if not os.path.exists(path):
                errors.append(f"script path in the condition doesn't exist: {path}")
    dec = C.load_decisions(root)
    if not dec["active"]:
        errors.append("qa/TEST_DECISIONS.md has no active decisions")
    work = p["sections"].get("Work list", "")
    # IDs under "Retired" in the work list may be retired; everything else must be active.
    work_main = re.split(r"(?mi)^###\s+Retired", work)[0]
    unknown = sorted({i for i in C.ID_IN_TEXT.findall(work_main) if i not in dec["active"]})
    if unknown:
        errors.append("work list cites decision IDs that are not active in TEST_DECISIONS.md: " + ", ".join(unknown[:30]))
    ranges = re.findall(r"([\w./\\-]+\.\w+):(\d+)-(\d+)", p["sections"].get("Context pack", ""))
    missing = sorted({f for f, _a, _b in ranges if not os.path.exists(os.path.join(root, f))})
    if missing:
        errors.append("context pack names files that don't exist: " + ", ".join(missing[:10]))
    turns = re.search(r"after (\d+) turns", cond or "")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "condition_chars": len(cond or ""),
            "sections": p["order"], "active_decisions": len(dec["active"]),
            "turn_cap": int(turns.group(1)) if turns else None}


def baseline_dirty(root):
    """{path: sha256} of files already modified/untracked before the worker starts (outside qa/)."""
    import hashlib
    code, out = C.git(root, "status", "--porcelain=v1", "-uall")
    base = {}
    if code != 0:
        return base
    for line in out.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if not path or path.startswith("qa/"):
            continue
        try:
            with open(os.path.join(root, path), "rb") as f:
                base[path] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            base[path] = "(missing)"
    return base


def classify(events, returncode, session_id, run_started):
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    verdicts = C.goal_verdicts(session_id, since_epoch=run_started)
    last = verdicts[-1] if verdicts else None
    if last and last["verdict"] == "met":
        status = "achieved"
    elif last and last["verdict"] == "impossible":
        status = "impossible"
    elif last and last["verdict"] == "cleared":
        status = "error"
    elif (result and result.get("is_error")) or returncode != 0:
        status = "error"
    elif last and last["verdict"] == "not_met":
        status = "not_met"
    else:
        status = "ended"
    return status, result, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--mode", default="auto", choices=["auto", "acceptEdits", "dontAsk"])
    ap.add_argument("--skill-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--check", action="store_true", help="validate qa/goal-prompt.md and exit")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--message")
    ap.add_argument("--allowed-tools", nargs="*")
    ap.add_argument("--model")
    ap.add_argument("--max-budget-usd")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    skill_dir = os.path.abspath(a.skill_dir)
    p = load_prompt(root)
    report = check(root, p)
    if a.check:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if report["ok"] else 1
    if not report["ok"]:
        print("qa/goal-prompt.md is not valid; run --check:\n- " + "\n- ".join(report["errors"]))
        return 1

    cond = p["condition"].replace("<SKILL_DIR>", skill_dir.replace("\\", "/"))
    with open(os.path.join(skill_dir, "references", "worker-contract.md"), "r", encoding="utf-8") as f:
        contract = f.read()
    contract += f"\n\nYour brief: `qa/goal-prompt.md`. SKILL_DIR: `{skill_dir}`.\n"

    st = C.load_state(root)
    w = st.get("worker", {})
    session = w.get("session_id") if a.resume else None
    if a.resume and not session:
        raise SystemExit("--resume: no worker session recorded; launch without --resume")
    if a.message:
        if not a.resume:
            raise SystemExit("--message needs --resume")
        adir = C.qa_path(root, "answers")
        os.makedirs(adir, exist_ok=True)
        n = 1 + sum(1 for x in os.listdir(adir) if x.startswith("fixup-"))
        ap_path = os.path.join(adir, f"fixup-{n}.md")
        if not a.dry_run:
            with open(ap_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"# Fix-up {n} from the orchestrator\n\n{a.message}\n")
        rel_p = C.rel(ap_path, root)
        room = 3900 - len(cond)
        msg = a.message if len(a.message) <= room - 200 else a.message[:max(0, room - 260)] + f"… (full text in {rel_p})"
        cond += (f"\nFIX-UP FROM THE ORCHESTRATOR (saved in {rel_p}); the goal is not met until it is done, "
                 f"the suite re-run and the report updated, all shown in the transcript: {msg}")

    exe, via_shim = C.claude_command()
    if via_shim:  # cmd.exe would split multi-line arguments
        cond = " ".join(cond.split())
        contract = " ".join(contract.split())
    cmd = exe + ["-p", "/goal " + cond, "--output-format", "stream-json", "--verbose",
                 "--permission-mode", a.mode, "--permission-prompts", "none",
                 "--append-system-prompt", contract]
    if session:
        cmd += ["--resume", session]
    allowed = list(a.allowed_tools or [])
    if a.mode == "acceptEdits":
        allowed = TEST_ALLOW + allowed
    if allowed:
        cmd += ["--allowedTools", ",".join(allowed)]
    if a.model:
        cmd += ["--model", a.model]
    if a.max_budget_usd:
        cmd += ["--max-budget-usd", str(a.max_budget_usd)]

    if a.dry_run:
        shown = [c if len(c) < 200 else c[:200] + f"…[{len(c)} chars]" for c in cmd]
        print(json.dumps({"cmd": shown, "condition_chars": len(cond), "resume": session}, indent=1))
        return 0

    os.makedirs(C.qa_path(root, "logs"), exist_ok=True)
    log_path = C.qa_path(root, "logs", "worker.jsonl")
    started = time.time()
    runs = int(w.get("runs", 0)) + 1
    st["worker"] = dict(w, status="running", run_started_at=started, runs=runs, mode=a.mode, ended_at=None,
                        started_at=w.get("started_at") if a.resume and w.get("started_at") else started,
                        log="qa/logs/worker.jsonl")
    if not a.resume:
        st["worker"]["baseline_dirty"] = baseline_dirty(root)  # check_tests.py ignores these if unchanged
    C.save_state(root, st)

    events = []
    session_id = session
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps({"type": "qa_run_start", "run": runs, "resume": bool(session), "at": started}) + "\n")
        try:
            proc = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            st = C.load_state(root)
            st["worker"].update(status="error", ended_at=time.time(), error=str(e))
            C.save_state(root, st)
            print(f"[qa-worker] could not start claude: {e}")
            return 1
        for line in proc.stdout:
            log.write(line)
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "system" and ev.get("subtype") == "init" and ev.get("session_id"):
                session_id = ev["session_id"]
                st = C.load_state(root)
                st["worker"]["session_id"] = session_id
                C.save_state(root, st)
            if ev.get("type") != "stream_event":
                events.append(ev)
        rc = proc.wait()

    status, result, last = classify(events, rc, session_id, started)
    rep = C.qa_path(root, "worker-report.md")
    if status == "ended" and os.path.exists(rep) and os.path.getmtime(rep) >= started:
        head = (C.read_text(rep) or "").splitlines()[:1]
        if head and "done" in head[0].lower():
            status = "achieved"
    st = C.load_state(root)
    st["worker"].update(status=status, ended_at=time.time(), exit_code=rc,
                        last_verdict_reason=(last or {}).get("reason", "")[:300])
    if result:
        st["worker"].update(turns=result.get("num_turns"), cost_usd=result.get("total_cost_usd"))
        if result.get("session_id"):
            st["worker"]["session_id"] = result["session_id"]
    C.save_state(root, st)
    wk = st["worker"]
    cost = f"${wk.get('cost_usd'):.2f}" if isinstance(wk.get("cost_usd"), (int, float)) else "?"
    print(f"[qa-worker] {status} · run {runs} · turns {wk.get('turns', '?')} · cost {cost} · exit {rc} · "
          f"report {'yes' if os.path.exists(rep) else 'MISSING'} · verdict: {wk.get('last_verdict_reason', '')[:160]} · "
          f"next: python check_tests.py --root .")
    return 0 if status == "achieved" else 2


if __name__ == "__main__":
    sys.exit(main())
