"""Shared helpers for the backend-checker scripts (standard library only)."""
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess

CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join("docs", ".backend-checks")

CODE_EXTS = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "typescript",
    ".py": "python", ".go": "go", ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".rs": "rust", ".scala": "scala",
    ".ex": "elixir", ".exs": "elixir", ".sql": "sql", ".prisma": "prisma", ".graphql": "graphql",
    ".gql": "graphql", ".vue": "vue", ".svelte": "svelte",
}
CONFIG_NAMES = re.compile(
    r"(^|/)(dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose\.ya?ml|nginx[^/]*\.conf|[^/]*\.nginx|"
    r"\.env\.(example|sample|template|dist)|vercel\.json|netlify\.toml|serverless\.ya?ml|app\.ya?ml|"
    r"settings\.py|application(-\w+)?\.(ya?ml|properties)|appsettings[^/]*\.json|config/[^/]+\.(json|ya?ml|toml))$",
    re.I)
MANIFEST_NAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "requirements-dev.txt", "requirements.in", "pyproject.toml", "poetry.lock",
    "uv.lock", "Pipfile", "Pipfile.lock", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "composer.lock", "Gemfile", "Gemfile.lock", "Cargo.toml", "Cargo.lock",
    "packages.lock.json", ".nvmrc", ".node-version", ".python-version", ".ruby-version", "runtime.txt",
}
EXCLUDE_DIRS = {
    "node_modules", "vendor", ".venv", "venv", "env", "dist", "build", "out", ".next", ".nuxt",
    "coverage", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", "target", "bin", "obj",
    ".turbo", ".cache", ".idea", ".vscode", "generated", "__generated__", ".svelte-kit", ".backend-checks",
}
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|e2e|fixtures?)/|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$|_test\.go$|"
    r"(^|/)conftest\.py$", re.I)

# Strong secret patterns: used for scanning and for masking anything that reaches a report.
SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("stripe_key", re.compile(r"\b[sr]k_(live|test)_[0-9A-Za-z]{16,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("connection_string", re.compile(r"\b(postgres(ql)?|mysql|mariadb|mongodb(\+srv)?|redis|amqps?|mssql)://[^:\s/'\"]+:([^@\s'\"]{3,})@")),
    ("generic_secret", re.compile(
        r"(?i)\b([a-z0-9_]*(?:secret|passwd|password|api[_-]?key|access[_-]?key|auth[_-]?token|private[_-]?key|client[_-]?secret)[a-z0-9_]*)"
        r"['\"]?\s*[:=]\s*(['\"]?)([^'\"\s,;#)]{6,})")),
]
PLACEHOLDER_VALUE = re.compile(r"(?i)^(\$\{|process\.env|os\.environ|getenv|env\(|<|\{\{|xxx|changeme|your[_-]|example|placeholder|todo|null|none|undefined|true|false|\*+$)")


def mask_value(v):
    v = str(v)
    return (v[:4] + "…[masked]") if len(v) > 4 else "…[masked]"


def mask_text(text):
    """Mask secret values in free text. Keeps the first 4 characters of each secret."""
    if not text:
        return text
    out = str(text)
    for kind, rx in SECRET_PATTERNS:
        if kind == "generic_secret":
            def _g(m):
                val = m.group(3)
                env_style = m.group(1).isupper() and "=" in m.group(0)
                if PLACEHOLDER_VALUE.match(val) or "[masked]" in val or not (m.group(2) or env_style):
                    return m.group(0)
                return m.group(0).replace(val, mask_value(val))
            out = rx.sub(_g, out)
        elif kind == "connection_string":
            out = rx.sub(lambda m: m.group(0).replace(m.group(4), mask_value(m.group(4))) if "[masked]" not in m.group(0) else m.group(0), out)
        elif kind == "private_key":
            continue
        else:
            out = rx.sub(lambda m: mask_value(m.group(0)), out)
    return out


def find_secrets(line, quoted_only=True):
    """Return [(kind, masked_preview)] for secrets on one line, skipping obvious placeholders.

    quoted_only: in source code a generic `password = x` only counts when x is a string literal.
    Env/config files pass False because `KEY=value` has no quotes.
    """
    hits = []
    for kind, rx in SECRET_PATTERNS:
        for m in rx.finditer(line):
            if kind == "generic_secret":
                val = m.group(3)
                if quoted_only and not m.group(2):
                    continue
                if PLACEHOLDER_VALUE.match(val) or "[masked]" in val:
                    continue
                hits.append((kind, m.group(1) + "=" + mask_value(val)))
            elif kind == "connection_string":
                hits.append((kind, mask_text(m.group(0))))
            else:
                hits.append((kind, mask_value(m.group(0))))
    return hits


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def state_path(root, *parts):
    return os.path.join(root, STATE_DIR, *parts)


def git(root, *args, timeout=60):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def load_registry():
    reg = load_json(os.path.join(CORE_DIR, "registry.json"), {"checks": []})
    return reg["checks"]


def registry_entry(check_id):
    for c in load_registry():
        if c["id"] == check_id:
            return c
    raise SystemExit(f"Unknown check '{check_id}'. Known: {[c['id'] for c in load_registry()]}")


def load_sections(entry):
    return load_json(os.path.join(CORE_DIR, entry["sections_file"]), {"sections": []})


def is_test_path(p):
    return bool(TEST_PATH.search(p))


def read_text(path, limit=2_000_000):
    try:
        with open(path, "rb") as f:
            b = f.read(limit + 1)
    except OSError:
        return None, None
    if len(b) > limit or b"\x00" in b[:4096]:
        return None, b
    return b.decode("utf-8", errors="replace"), b

# --------------------------------------------------------------------------- brace languages
# Shared by quality_scan.py and perf_scan.py: a heuristic function/block tracker for brace languages.
BRACE_LANGS = {"javascript", "typescript", "go", "java", "kotlin", "csharp", "php", "rust", "scala", "vue", "svelte"}
CONTROL = re.compile(r"^\s*(\}\s*)?(else\s+if|if|else|for|foreach|while|switch|try|catch|finally|do|select)\b|^\s*(case|default)\b.*:\s*\{?\s*$")
FN_START = [
    re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?function\s*\*?\s*([\w$]*)\s*\("),
    re.compile(r"^\s*(export\s+)?(const|let|var)\s+([\w$]+)\s*=\s*(async\s*)?(\([^)]*\)|[\w$]+)\s*(:\s*[^=]+)?=>"),
    re.compile(r"^\s*(public|private|protected|internal|static|async|override|final|\s)*\s*([\w$<>\[\],]+\s+)?([\w$]+)\s*\([^;]*\)\s*(:\s*[\w<>\[\]|, .]+)?\s*(throws [\w, .]+)?\s*\{\s*$"),
    re.compile(r"^\s*func\s+(\([^)]*\)\s*)?([\w]+)\s*\("),
    re.compile(r"^\s*(public|private|protected|static|\s)*function\s+([\w]+)\s*\("),
    re.compile(r"""\.(get|post|put|patch|delete|use|all|on)\s*\(\s*(['"`][^'"`]*['"`])?.*(=>|function\s*\()"""),
]
NOT_FN = re.compile(r"^\s*(if|for|while|switch|catch|return|else|do|try|with|new|typeof|await)\b")


def strip_strings(line):
    return re.sub(r"""(['"`])(?:\\.|(?!\1).)*\1""", "''", line.split("//")[0] if "://" not in line else line)


def brace_functions(lines):
    """Yield (name, start, end, max_control_depth) using brace matching. Heuristic, good enough for candidates."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        name = None
        if not NOT_FN.match(line):
            for rx in FN_START:
                m = rx.search(line)
                if m:
                    groups = [g for g in m.groups() if g and re.match(r"^['\"`]?[\w$/:.\-]+['\"`]?$", g.strip())]
                    name = groups[-1].strip() if groups else "(anonymous)"
                    break
        if name is None:
            i += 1
            continue
        depth, started, stack, maxd = 0, False, [], 0
        j = i
        while j < n:
            s = strip_strings(lines[j])
            is_ctrl = bool(CONTROL.match(lines[j]))
            for ch in s:
                if ch == "{":
                    depth += 1
                    started = True
                    stack.append(is_ctrl and depth > 1)
                    maxd = max(maxd, sum(stack))
                elif ch == "}":
                    depth -= 1
                    if stack:
                        stack.pop()
            if started and depth <= 0:
                break
            if not started and j - i > 3:
                break
            j += 1
        if started:
            out.append((name, i + 1, j + 1, maxd))
            i += 1  # nested functions are reported separately
        else:
            i += 1
    return out

def brace_block_end(lines, i, max_scan=4):
    """1-based end line of the `{...}` block that opens on (or within max_scan lines after) line index i, or None."""
    depth, started = 0, False
    for j in range(i, len(lines)):
        for ch in strip_strings(lines[j]):
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth <= 0:
            return j + 1
        if not started and j - i >= max_scan:
            return None
    return len(lines) if started else None
