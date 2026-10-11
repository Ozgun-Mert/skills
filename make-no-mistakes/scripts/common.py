"""Shared helpers for the make-no-mistakes scripts (standard library only)."""
import json
import os
import re
import shutil
import time

MNM = "mnm"
SECTIONS = ["Goal condition", "Context pack", "Ownership", "Acceptance", "Best practices",
            "Constraints", "Questions", "Report"]
# Paths that never count as a piece's change (tool caches, build output, mnm's own folders).
IGNORED_CHANGE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".svelte-kit", ".next", ".nuxt", ".turbo", ".cache", "dist", "build", "out",
    "coverage", "test-results", "playwright-report", "blob-report", ".output", "target", "mnm",
    ".idea", ".vscode", "tmp",
}
IGNORED_CHANGE_FILES = re.compile(r"\.(pyc|pyo|log|tsbuildinfo)$|(^|/)\.DS_Store$|(^|/)next-env\.d\.ts$")


def mnm_path(root, *parts):
    return os.path.join(root, MNM, *parts)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for _ in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: reader holds the file for a moment
            time.sleep(0.1)
    os.replace(tmp, path)


class StateLock:
    """Cross-process lock around mnm/state.json (several launchers run in parallel)."""

    def __init__(self, root, timeout=30):
        self.path = mnm_path(root, ".state.lock")
        self.timeout = timeout

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                try:  # stale lock from a crashed process
                    if time.time() - os.path.getmtime(self.path) > 60:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise SystemExit("mnm/state.json is locked; retry in a moment")
                time.sleep(0.05)

    def __exit__(self, *exc):
        os.close(self.fd)
        try:
            os.remove(self.path)
        except OSError:
            pass


def load_state(root):
    return load_json(mnm_path(root, "state.json"), {}) or {}


def update_state(root, fn):
    """Apply fn(state) under the lock and save. Returns the new state."""
    with StateLock(root):
        st = load_state(root)
        fn(st)
        save_json(mnm_path(root, "state.json"), st)
        return st


def update_piece(root, piece, **fields):
    def fn(st):
        st.setdefault("pieces", {}).setdefault(piece, {}).update(fields)
    return update_state(root, fn)


# --------------------------------------------------------------------------- prompt files

def parse_front_matter(text):
    """Minimal YAML subset: `key: value` and `key:` followed by `  - item` lines."""
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None, text
    meta, key = {}, None
    for raw in m.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s*-\s+(.*)$", line)
        if item and key:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(item.group(1).strip().strip("'\""))
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            elif val:
                meta[key] = val.strip("'\"")
            else:
                meta[key] = []
    return meta, text[m.end():]


def sections(body):
    """Return {section title: content} for `## Title` headings, in order."""
    out, order = {}, []
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", body)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        out[title] = parts[i + 1]
        order.append(title)
    return out, order


def goal_condition(section_text):
    m = re.search(r"```(?:text)?\s*\n(.*?)\n```", section_text or "", re.S)
    return m.group(1).strip() if m else None


def load_prompts(root):
    """Return {piece: {file, meta, sections, order, condition}} for mnm/prompts/*.md."""
    pdir = mnm_path(root, "prompts")
    out = {}
    if not os.path.isdir(pdir):
        return out
    for name in sorted(os.listdir(pdir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(pdir, name)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        meta, body = parse_front_matter(text)
        secs, order = sections(body)
        piece = (meta or {}).get("piece") or name[:-3].replace("prompt", "") or name[:-3]
        out.setdefault(piece, []).append({
            "file": f"{MNM}/prompts/{name}", "meta": meta, "sections": secs, "order": order,
            "condition": goal_condition(secs.get("Goal condition")),
        })
    return out


def ownership(meta):
    own = (meta or {}).get("ownership") or []
    return [own] if isinstance(own, str) else own


def depends(meta):
    dep = (meta or {}).get("depends_on") or []
    return [dep] if isinstance(dep, str) else dep


# --------------------------------------------------------------------------- globs

def glob_regex(glob):
    g = glob.replace("\\", "/")
    if g.startswith("./"):
        g = g[2:]
    rx, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            rx += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            rx += ".*"
            i += 2
        elif g[i] == "*":
            rx += "[^/]*"
            i += 1
        elif g[i] == "?":
            rx += "[^/]"
            i += 1
        else:
            rx += re.escape(g[i])
            i += 1
    return re.compile("^" + rx + "$")


def matches(path, globs):
    path = path.replace("\\", "/")
    return any(glob_regex(g).match(path) for g in globs)


def _literal_prefix(glob):
    m = re.search(r"[*?\[]", glob)
    return glob if not m else glob[:m.start()]


def globs_overlap(a, b):
    """Conservative check whether two globs can match a common path."""
    a, b = a.replace("\\", "/"), b.replace("\\", "/")
    wa, wb = bool(re.search(r"[*?]", a)), bool(re.search(r"[*?]", b))
    if not wa and not wb:
        return a == b
    if not wa:
        return bool(glob_regex(b).match(a))
    if not wb:
        return bool(glob_regex(a).match(b))
    pa, pb = _literal_prefix(a), _literal_prefix(b)
    if not (pa.startswith(pb) or pb.startswith(pa)):
        return False
    ra, rb = a[len(pa):], b[len(pb):]
    if pa == pb and "/" not in ra and "/" not in rb and "**" not in ra + rb:
        ca = {c for c in re.split(r"[*?]", ra) if len(c) >= 2}
        cb = {c for c in re.split(r"[*?]", rb) if len(c) >= 2}
        if ca and cb and not (ca <= cb or cb <= ca):
            return False
    return True


# --------------------------------------------------------------------------- changes

def changed_since(root, since_epoch):
    """Files (repo-relative) created or modified after since_epoch, minus caches/build output."""
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in IGNORED_CHANGE_DIRS]
        for f in files:
            full = os.path.join(d, f)
            relp = os.path.relpath(full, root).replace("\\", "/")
            if IGNORED_CHANGE_FILES.search(relp):
                continue
            try:
                if os.path.getmtime(full) >= since_epoch - 1:
                    out.append(relp)
            except OSError:
                pass
    return sorted(out)


# --------------------------------------------------------------------------- claude binary

def claude_command():
    """Return the argv prefix that runs Claude Code without a cmd.exe shim.

    On Windows `claude` is usually claude.cmd, and cmd.exe would mangle multi-line arguments.
    Resolve the real executable from the shim when possible.
    """
    path = shutil.which("claude")
    if not path:
        raise SystemExit("`claude` CLI not found on PATH")
    if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                shim = f.read()
        except OSError:
            shim = ""
        base = os.path.dirname(path)
        exe = re.search(r'"%dp0%\\([^"]+?\.exe)"', shim)
        if exe:
            cand = os.path.join(base, exe.group(1))
            if os.path.exists(cand):
                return [cand], False
        js = re.search(r'"%dp0%\\([^"]+?\.(?:js|cjs|mjs))"', shim)
        node = shutil.which("node")
        if js and node:
            cand = os.path.join(base, js.group(1))
            if os.path.exists(cand):
                return [node, cand], False
        return [path], True  # last resort: shim (arguments must be single-line)
    return [path], False


def transcript_path(session_id):
    """Find a session's transcript: <config dir>/projects/<mangled cwd>/<session_id>.jsonl."""
    if not session_id:
        return None
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    projects = os.path.join(base, "projects")
    try:
        for d in os.listdir(projects):
            p = os.path.join(projects, d, f"{session_id}.jsonl")
            if os.path.exists(p):
                return p
    except OSError:
        pass
    return None


def goal_verdicts(session_id, since_epoch=None):
    """Return the /goal evaluator verdicts recorded in the session transcript, oldest first.

    Each item: {"verdict": "met"|"not_met"|"impossible"|"cleared", "reason": str, "at": iso}.
    The evaluator writes `attachment.type == "goal_status"` records (stream-json doesn't carry
    them); an unrecoverable error writes a system message starting "Goal cleared after".
    """
    path = transcript_path(session_id)
    out = []
    if not path:
        return out
    try:
        f = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return out
    with f:
        for line in f:
            if "goal" not in line.lower():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ts = e.get("timestamp")
            if since_epoch and ts:
                try:
                    import datetime as _dt
                    t = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    if t < since_epoch - 2:
                        continue
                except ValueError:
                    pass
            att = e.get("attachment") or {}
            if att.get("type") == "goal_status":
                if att.get("sentinel"):
                    continue  # the "goal set" marker, not a verdict
                if att.get("impossible") or str(att.get("verdict", "")).lower() == "impossible":
                    v = "impossible"
                elif att.get("met"):
                    v = "met"
                else:
                    v = "not_met"
                out.append({"verdict": v, "reason": (att.get("reason") or "")[:500], "at": ts})
            elif e.get("type") == "system" and "goal cleared after" in str(e.get("content", "")).lower():
                out.append({"verdict": "cleared", "reason": str(e.get("content"))[:500], "at": ts})
            elif e.get("type") == "system" and "impossible" in str(e.get("content", "")).lower() \
                    and "goal" in str(e.get("content", "")).lower():
                out.append({"verdict": "impossible", "reason": str(e.get("content"))[:500], "at": ts})
    return out


def now():
    return time.time()
