"""Concatenate the files a run must analyze into a few line-numbered parts.

Reading 3-5 part files costs far fewer tool round-trips than opening 60 files one by one, and in
health mode the orchestrator reads them once so the forked agents share them from the prompt cache.

Usage: python bundle.py --root . --plans docs/.backend-checks/plan-security.json [more plans...] [--max-lines 1500]
Writes docs/.backend-checks/bundle/part-NN.txt and prints the part list.
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plans", nargs="+", required=True)
    ap.add_argument("--max-lines", type=int, default=1500)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    files = []
    for pp in a.plans:
        plan = C.load_json(pp if os.path.isabs(pp) else os.path.join(root, pp))
        if not plan:
            print(json.dumps({"error": f"plan not found: {pp}"}))
            return 2
        if plan.get("skip"):
            continue
        for f in plan["files_to_analyze"]:
            if f["path"] not in files:
                files.append(f["path"])
    out_dir = C.state_path(root, "bundle")
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    parts, buf, n = [], [], 0

    def flush():
        nonlocal buf, n
        if buf:
            p = os.path.join(out_dir, f"part-{len(parts) + 1:02d}.txt")
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(buf) + "\n")
            parts.append({"path": C.rel(p, root), "lines": n})
            buf, n = [], 0

    for path in files:
        text, _ = C.read_text(os.path.join(root, path))
        if text is None:
            continue
        lines = text.splitlines()
        chunk_start = 0
        while chunk_start < len(lines) or (not lines and chunk_start == 0):
            room = a.max_lines - n
            if room < 40 and buf:
                flush()
                room = a.max_lines
            end = min(len(lines), chunk_start + room)
            label = f"===== {path} ({len(lines)} lines)" + (f" [lines {chunk_start + 1}-{end}]" if chunk_start or end < len(lines) else "") + " ====="
            buf.append(label)
            buf.extend(f"{i + 1:>5}| {lines[i]}" for i in range(chunk_start, end))
            n += end - chunk_start + 1
            chunk_start = end
            if not lines:
                break
            if chunk_start < len(lines):
                flush()
    flush()
    print(json.dumps({"files": len(files), "parts": parts}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
