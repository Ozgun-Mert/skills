"""Run one make-no-mistakes piece as a headless /goal worker and record the outcome.

Builds:  claude -p "/goal <condition>" --output-format stream-json --verbose
                --permission-mode <mode> --permission-prompts none
                --append-system-prompt <references/worker-contract.md>
                [--resume <session_id>] [--allowedTools ...] [--model ...] [--max-budget-usd ...]
The condition comes from the piece's prompt file (## Goal condition). Output streams to
mnm/logs/<piece>.jsonl. session_id, status, turns and cost go to mnm/state.json.

Run it from the orchestrator with Bash `run_in_background: true`. It blocks until the worker
exits, then prints one summary line, so the background notification says how it went.

--resume continues the piece's last session (it keeps everything it already read) and sets the
goal again. With --message, the text is first saved as an answer file in mnm/answers/<piece>/,
which the goal condition requires the worker to apply.

Usage:
  python launch_worker.py --root . --piece backend --mode auto --skill-dir <SKILL_DIR>
  python launch_worker.py --root . --piece backend --resume --message "Use 404, not 403, for ..."
  python launch_worker.py ... --dry-run     # print the command only
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

STACK_ALLOW = [  # used with --mode acceptEdits: build/test/install commands only
    "Bash(npm *)", "Bash(npx *)", "Bash(bun *)", "Bash(bunx *)", "Bash(pnpm *)", "Bash(node *)",
    "Bash(uv *)", "Bash(python *)", "Bash(python3 *)", "Bash(pytest *)", "Bash(ruff *)",
    "Bash(mypy *)", "Bash(pip-audit *)", "Bash(alembic *)", "Bash(go *)", "Bash(gofmt *)",
    "Bash(sqlc *)", "Bash(goose *)", "Bash(govulncheck *)", "Bash(staticcheck *)",
    "Bash(docker compose *)", "Bash(docker-compose *)", "Bash(make *)", "Bash(curl *)",
    "Bash(cat *)", "Bash(ls *)", "Bash(mkdir *)", "Bash(type *)", "Bash(git status *)",
    "Bash(git diff *)", "Read", "Edit", "Write", "Glob", "Grep",
]


def find_prompt(root, piece):
    prompts = C.load_prompts(root)
    if piece not in prompts:
        raise SystemExit(f"unknown piece '{piece}'. Known: {sorted(prompts)}")
    e = prompts[piece][0]
    if not e["condition"]:
        raise SystemExit(f"{e['file']} has no goal condition")
    return e


def next_answer_path(root, piece):
    d = C.mnm_path(root, "answers", piece)
    os.makedirs(d, exist_ok=True)
    n = 1 + sum(1 for f in os.listdir(d) if f.startswith("orchestrator-"))
    return os.path.join(d, f"orchestrator-{n}.md")


def classify(events, returncode, session_id, run_started):
    """Decide the run status from the /goal verdicts in the transcript, then the result event."""
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
        status = "not_met"  # loop stopped (turn cap, no progress) with the goal unmet
    else:
        status = "ended"  # no verdict found: check the report
    return status, result, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--piece", required=True)
    ap.add_argument("--mode", default="auto", choices=["auto", "acceptEdits", "dontAsk"])
    ap.add_argument("--skill-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--resume", action="store_true", help="continue the piece's last session")
    ap.add_argument("--message", help="with --resume: instruction saved as an answer file first")
    ap.add_argument("--allowed-tools", nargs="*", help="extra allow rules (acceptEdits mode adds a stack allowlist)")
    ap.add_argument("--model")
    ap.add_argument("--max-budget-usd")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    skill_dir = os.path.abspath(a.skill_dir)
    entry = find_prompt(root, a.piece)
    cond = entry["condition"].replace("<SKILL_DIR>", skill_dir.replace("\\", "/"))
    contract_path = os.path.join(skill_dir, "references", "worker-contract.md")
    with open(contract_path, "r", encoding="utf-8") as f:
        contract = f.read()
    contract += f"\n\nYour piece: `{a.piece}`. Your prompt file: `{entry['file']}`. SKILL_DIR: `{skill_dir}`.\n"

    st = C.load_state(root)
    pinfo = st.get("pieces", {}).get(a.piece, {})
    session = pinfo.get("session_id") if a.resume else None
    if a.resume and not session:
        raise SystemExit(f"--resume: no session_id recorded for '{a.piece}'; launch it without --resume")
    if a.message:
        if not a.resume:
            raise SystemExit("--message needs --resume")
        p = next_answer_path(root, a.piece)
        if not a.dry_run:
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"# From the orchestrator\n\n{a.message}\n")
        # Put the fix-up in the condition too, so the evaluator only says "met" once it is done.
        rel_p = os.path.relpath(p, root).replace("\\", "/")
        room = 3900 - len(cond)
        msg = a.message if len(a.message) <= room - 200 else a.message[:max(0, room - 260)] + f"… (full text in {rel_p})"
        cond += (f"\nFIX-UP FROM THE ORCHESTRATOR (saved in {rel_p}); the goal is not met until it is done "
                 f"and its effect is shown in the transcript: {msg}")

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
        allowed = STACK_ALLOW + allowed
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

    logs = C.mnm_path(root, "logs")
    os.makedirs(logs, exist_ok=True)
    for d in ("questions", "reports", os.path.join("answers", a.piece)):
        os.makedirs(C.mnm_path(root, d), exist_ok=True)
    log_path = os.path.join(logs, f"{a.piece}.jsonl")
    started = time.time()
    runs = int(pinfo.get("runs", 0)) + 1
    C.update_piece(root, a.piece, status="running", started_at=pinfo.get("started_at") if a.resume and pinfo.get("started_at") else started,
                   run_started_at=started, runs=runs, file=entry["file"], mode=a.mode, ended_at=None,
                   log=f"mnm/logs/{a.piece}.jsonl")

    env = dict(os.environ, MNM_PIECE=a.piece)
    events = []
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps({"type": "mnm_run_start", "run": runs, "resume": bool(session),
                              "at": started}) + "\n")
        try:
            proc = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, env=env, text=True,
                                    encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            C.update_piece(root, a.piece, status="error", ended_at=time.time(), error=str(e))
            print(f"[{a.piece}] could not start claude: {e}")
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
                C.update_piece(root, a.piece, session_id=ev["session_id"])
            if ev.get("type") != "stream_event":
                events.append(ev)
        rc = proc.wait()

    session_id = C.load_state(root).get("pieces", {}).get(a.piece, {}).get("session_id")
    status, result, last = classify(events, rc, session_id, started)
    report = C.mnm_path(root, "reports", f"{a.piece}.md")
    if status == "ended" and os.path.exists(report) and os.path.getmtime(report) >= started:
        with open(report, "r", encoding="utf-8", errors="replace") as f:
            head = f.readline().lower()
        if "achieved" in head:
            status = "achieved"
    fields = {"status": status, "ended_at": time.time(), "exit_code": rc,
              "last_verdict_reason": (last or {}).get("reason", "")[:300]}
    if result:
        fields.update(turns=result.get("num_turns"), cost_usd=result.get("total_cost_usd"),
                      session_id=result.get("session_id") or pinfo.get("session_id"))
        if result.get("session_id") is None:
            fields.pop("session_id")
    C.update_piece(root, a.piece, **fields)
    cost = f"${fields.get('cost_usd'):.2f}" if isinstance(fields.get("cost_usd"), (int, float)) else "?"
    print(f"[{a.piece}] {status} · run {runs} · turns {fields.get('turns', '?')} · cost {cost} · "
          f"exit {rc} · report {'yes' if os.path.exists(report) else 'MISSING'} · "
          f"next: python worker_status.py --root . --piece {a.piece}")
    return 0 if status == "achieved" else 2


if __name__ == "__main__":
    sys.exit(main())
