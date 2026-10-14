"""Shared helpers for the qa-backend scripts (standard library only)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

QA = "qa"
# Folders never scanned (deps, build output, caches, the skill's own folder).
EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".svelte-kit", ".next", ".nuxt", ".turbo", ".cache", "dist", "build", "out",
    "coverage", "test-results", "playwright-report", ".output", "target", "bin", "obj", "vendor",
    QA, ".idea", ".vscode", "tmp", ".terraform", ".gradle", ".dart_tool", "Pods", "docs",
}
CODE_EXTS = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "typescript",
    ".py": "python", ".go": "go", ".java": "java", ".kt": "kotlin", ".cs": "csharp",
    ".php": "php", ".rb": "ruby", ".rs": "rust", ".scala": "scala",
}
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|e2e|testing|fixtures?|mocks?|__mocks__)(/|$)|"
    r"(\.|_|-)(test|spec)s?\.[a-z]+$|(^|/)test_[^/]+\.py$|_test\.go$|(Test|Tests|IT)\.(java|kt|cs)$|"
    r"(^|/)conftest\.py$")
GENERATED_PATH = re.compile(
    r"(^|/)(migrations?|alembic|seeds?|seeders|generated|__generated__|gen|proto|prisma/client)(/|$)|"
    r"\.(d\.ts|pb\.go|pb\.ts|min\.js|generated\.\w+)$|_pb2(_grpc)?\.py$|(^|/)(\w+\.)?config\.(js|ts|mjs|cjs)$")

SECRET_KEY_NAME = re.compile(r"(?i)(secret|token|password|passwd|pwd|api[_-]?key|private|credential|dsn|_url$|^url$)")


# --------------------------------------------------------------------------- paths / json

def qa_path(root, *parts):
    return os.path.join(root, QA, *parts)


def rel(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


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
        except PermissionError:  # Windows: a reader holds the file for a moment
            time.sleep(0.1)
    os.replace(tmp, path)


def load_state(root):
    return load_json(qa_path(root, "state.json"), {}) or {}


def save_state(root, st):
    save_json(qa_path(root, "state.json"), st)


def update_state(root, **fields):
    st = load_state(root)
    st.update(fields)
    save_state(root, st)
    return st


def read_text(path, limit=2_000_000):
    try:
        if os.path.getsize(path) > limit:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def sha(text, n=12):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:n]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def git(root, *args, timeout=30):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def vscode_link(root, relpath, line=1, col=1):
    """vscode://file/<absolute path>:<line>:<col>, with forward slashes and URL-safe spaces."""
    p = os.path.abspath(os.path.join(root, relpath)).replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p  # C:/x -> /C:/x  (vscode://file/C:/x)
    p = p.replace(" ", "%20").replace("#", "%23").replace("(", "%28").replace(")", "%29")
    return f"vscode://file{p}:{int(line or 1)}:{int(col or 1)}"


# --------------------------------------------------------------------------- secrets

SECRET_VALUE_PATTERNS = [
    (re.compile(r"(?i)\b((?:sk|pk|rk)_(?:live|test)_)[A-Za-z0-9]{8,}"), r"\1****"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA****"),
    (re.compile(r"\b(gh[pousr]_)[A-Za-z0-9]{20,}\b"), r"\1****"),
    (re.compile(r"\b(xox[abprs]-)[A-Za-z0-9-]{10,}"), r"\1****"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "eyJ****"),
    (re.compile(r"(?i)\b((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqp)://)[^\s'\"]+"), r"\1****"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)(\s*[=:]\s*['\"]?)[^\s'\",]{4,}"), r"\1\2****"),
]


def mask_text(text):
    if not text:
        return text
    for rx, repl in SECRET_VALUE_PATTERNS:
        text = rx.sub(repl, text)
    return text


# --------------------------------------------------------------------------- env files

def parse_env_file(path):
    """Return {KEY: value} from a dotenv-style file. Values stay in memory; never print them."""
    out = {}
    text = read_text(path, limit=500_000)
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if " #" in v and not v.startswith(("'", '"')):
            v = v.split(" #", 1)[0].strip()
        out[k] = v.strip("'\"")
    return out


# --------------------------------------------------------------------------- source walking

def walk_code(root, src_dirs, include_tests=False):
    """Yield (relpath, lang) for code files under src_dirs (relative to root)."""
    seen = set()
    for sd in src_dirs:
        base = os.path.join(root, sd)
        if os.path.isfile(base):
            ext = os.path.splitext(base)[1].lower()
            if ext in CODE_EXTS:
                yield rel(base, root), CODE_EXTS[ext]
            continue
        for d, dirs, files in os.walk(base):
            dirs[:] = sorted(x for x in dirs if x not in EXCLUDE_DIRS and not x.startswith("."))
            for f in sorted(files):
                ext = os.path.splitext(f)[1].lower()
                if ext not in CODE_EXTS:
                    continue
                rp = rel(os.path.join(d, f), root)
                if rp in seen:
                    continue
                seen.add(rp)
                if not include_tests and TEST_PATH.search(rp):
                    continue
                yield rp, CODE_EXTS[ext]


# --------------------------------------------------------------------------- claude binary + /goal

def claude_command():
    """Return (argv prefix, via_shim) that runs Claude Code without a cmd.exe shim when possible.

    On Windows `claude` is usually claude.cmd, and cmd.exe would mangle multi-line arguments.
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
    """/goal evaluator verdicts from the session transcript, oldest first.

    Each item: {"verdict": "met"|"not_met"|"impossible"|"cleared", "reason": str, "at": iso}.
    """
    import datetime as _dt
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
                    t = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    if t < since_epoch - 2:
                        continue
                except ValueError:
                    pass
            att = e.get("attachment") or {}
            content = str(e.get("content", "")).lower()
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
            elif e.get("type") == "system" and "goal cleared after" in content:
                out.append({"verdict": "cleared", "reason": str(e.get("content"))[:500], "at": ts})
            elif e.get("type") == "system" and "impossible" in content and "goal" in content:
                out.append({"verdict": "impossible", "reason": str(e.get("content"))[:500], "at": ts})
    return out


# --------------------------------------------------------------------------- decisions file

DECISION_ID = re.compile(r"^(F\d{3,}-D\d+|G-\d+|S-\d+|SEC-\d+|OBV-\d+)$")
ID_IN_TEXT = re.compile(r"\b(F\d{3,}-D\d+|G-\d+|S-\d+|SEC-\d+|OBV-\d+)\b")
FUNC_ID_IN_TEXT = re.compile(r"(?:\b|(?<=Test))(F\d{3,})(?=\b|-D|_)")  # "F012 name", "[F012-D3]", "TestF012_Name"


def load_decisions(root):
    """Parse qa/TEST_DECISIONS.md. Returns {"active": {id: section}, "retired": set, "skipped_functions": set}."""
    text = read_text(qa_path(root, "TEST_DECISIONS.md")) or ""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    active, retired, skipped = {}, set(), set()
    section = ""
    func_status = {}
    current_func = None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.*)$", line)
        if h:
            section = h.group(1).strip()
            m = re.match(r"^(F\d{3,})\b", section)
            current_func = m.group(1) if m else None
            continue
        if current_func:
            st = re.search(r"status:\s*`?([a-z_]+)", line)
            if st:
                func_status[current_func] = st.group(1)
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
        if not cells:
            continue
        cid = cells[0].strip("` *")
        if not DECISION_ID.match(cid):
            continue
        if section.lower().startswith("retired"):
            retired.add(cid)
        else:
            active[cid] = section
    for fid, st in func_status.items():
        if st in ("skipped", "retired", "removed"):
            skipped.add(fid)
    for cid in list(active):
        fid = cid.split("-D")[0] if cid.startswith("F") else None
        if fid and fid in skipped:
            active.pop(cid)
            retired.add(cid)
    for cid in retired:
        active.pop(cid, None)
    return {"active": active, "retired": retired, "skipped_functions": skipped}
