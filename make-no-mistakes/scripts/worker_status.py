"""Compact status of make-no-mistakes workers, so the orchestrator never reads raw logs.

  python worker_status.py --root .                 # one line per piece + open questions count
  python worker_status.py --root . --piece backend # detail for one piece (few lines)
  python worker_status.py --root . --questions     # unanswered worker questions as JSON

A question is open while mnm/answers/<piece>/<question-id>.md doesn't exist.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def open_questions(root):
    qdir = C.mnm_path(root, "questions")
    out = []
    if not os.path.isdir(qdir):
        return out
    for name in sorted(os.listdir(qdir)):
        if not name.endswith(".json"):
            continue
        q = C.load_json(os.path.join(qdir, name), None)
        if not isinstance(q, dict):
            out.append({"id": name[:-5], "file": f"mnm/questions/{name}", "error": "unreadable JSON"})
            continue
        qid = q.get("id") or name[:-5]
        piece = q.get("piece") or qid.rsplit("-", 1)[0]
        if os.path.exists(C.mnm_path(root, "answers", piece, f"{qid}.md")):
            continue
        q.update(id=qid, piece=piece, file=f"mnm/questions/{name}")
        out.append(q)
    return out


def last_assistant_text(log_path, limit=300):
    """Last assistant text block in the piece's stream-json log (read from the end)."""
    try:
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 400_000))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(tail):
        if '"type":"assistant"' not in line.replace(" ", ""):
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        for b in reversed(e.get("message", {}).get("content") or []):
            if b.get("type") == "text" and b.get("text", "").strip():
                return " ".join(b["text"].split())[:limit]
    return ""


def fmt_dur(info):
    s, e = info.get("run_started_at") or info.get("started_at"), info.get("ended_at")
    if not s:
        return "-"
    secs = int((e or time.time()) - s)
    return f"{secs // 60}m{secs % 60:02d}s"


def piece_detail(root, piece, info):
    report = C.mnm_path(root, "reports", f"{piece}.md")
    verdicts = C.goal_verdicts(info.get("session_id"), since_epoch=info.get("run_started_at"))
    lines = [
        f"piece: {piece} · status: {info.get('status', 'pending')} · run {info.get('runs', 0)} · "
        f"duration {fmt_dur(info)} · turns {info.get('turns', '?')} · cost "
        + (f"${info['cost_usd']:.2f}" if isinstance(info.get("cost_usd"), (int, float)) else "?"),
        f"session: {info.get('session_id', '-')} · exit: {info.get('exit_code', '-')} · "
        f"report: {'mnm/reports/' + piece + '.md' if os.path.exists(report) else 'MISSING'}",
    ]
    if verdicts:
        v = verdicts[-1]
        lines.append(f"last /goal verdict ({len(verdicts)} total): {v['verdict']} — {v['reason'][:300]}")
    elif info.get("last_verdict_reason"):
        lines.append(f"last /goal verdict: {info['last_verdict_reason'][:300]}")
    if info.get("log"):
        txt = last_assistant_text(os.path.join(root, info["log"]))
        if txt:
            lines.append(f"last message: {txt}")
    qs = [q for q in open_questions(root) if q.get("piece") == piece]
    if qs:
        lines.append(f"open questions: {', '.join(q['id'] for q in qs)}")
    if os.path.exists(report):
        with open(report, "r", encoding="utf-8", errors="replace") as f:
            head = f.readline().strip()
        lines.append(f"report header: {head}")
    return "\n".join(lines)


def watch(root, minutes, interval):
    """For the Monitor tool: one line per new open question or piece status change.

    Exits after `minutes` (Monitor watches end at 30 min at most) or when no piece is running
    and no question is open; the orchestrator starts it again while workers run.
    """
    seen_q, seen_status = set(), {}
    for p, info in C.load_state(root).get("pieces", {}).items():
        seen_status[p] = info.get("status")
    deadline = time.time() + minutes * 60
    print(f"watching mnm/ for questions and status changes for {minutes} min", flush=True)
    while time.time() < deadline:
        for q in open_questions(root):
            if q["id"] not in seen_q:
                seen_q.add(q["id"])
                print(f"QUESTION {q['id']} ({q.get('kind', 'product')}, piece {q.get('piece')}): "
                      f"{' '.join(str(q.get('question', '')).split())[:200]}", flush=True)
        pieces = C.load_state(root).get("pieces", {})
        for p, info in pieces.items():
            s = info.get("status")
            if seen_status.get(p) != s:
                seen_status[p] = s
                print(f"STATUS {p} → {s}", flush=True)
        if not any(i.get("status") == "running" for i in pieces.values()) and not open_questions(root):
            print("IDLE no worker running and no open question", flush=True)
            return 0
        time.sleep(interval)
    print("WATCH_END restart the watch if workers are still running", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--piece")
    ap.add_argument("--questions", action="store_true")
    ap.add_argument("--watch", action="store_true", help="stream new questions/status changes (for Monitor)")
    ap.add_argument("--minutes", type=float, default=29)
    ap.add_argument("--interval", type=float, default=5)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    st = C.load_state(root)
    pieces = st.get("pieces", {})

    if a.watch:
        return watch(root, a.minutes, a.interval)
    if a.questions:
        print(json.dumps(open_questions(root), ensure_ascii=False, indent=1))
        return 0
    if a.piece:
        if a.piece not in pieces:
            print(f"unknown piece '{a.piece}'. Known: {sorted(pieces)}")
            return 1
        print(piece_detail(root, a.piece, pieces[a.piece]))
        return 0

    print(f"phase: {st.get('phase', '?')} · mode: {st.get('mode', '?')}")
    for i, wave in enumerate(st.get("waves", [])):
        cells = []
        for p in wave:
            info = pieces.get(p, {})
            cost = f" ${info['cost_usd']:.2f}" if isinstance(info.get("cost_usd"), (int, float)) else ""
            cells.append(f"{p}={info.get('status', 'pending')} ({fmt_dur(info)}{cost})")
        print(f"W{i}: " + " · ".join(cells))
    total = sum(v.get("cost_usd") or 0 for v in pieces.values() if isinstance(v.get("cost_usd"), (int, float)))
    q = open_questions(root)
    print(f"total worker cost: ${total:.2f} · open questions: {len(q)}"
          + (f" ({', '.join(x['id'] for x in q)})" if q else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
