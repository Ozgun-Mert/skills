"""Map every function and route in the backend, with stable IDs and change detection.

Writes qa/function-map.json:
  functions: id (stable F001…), key (file::name[#n]), name, file, start, end, lines, lang, kind,
             exported, trivial, route ({method, path} or null), hash (normalized body), status
  routes:    every route registration found, linked to its handler function when possible
Statuses against qa/state.json: new (never decided), changed (hash differs from when it was
decided), unchanged, skipped (user skipped it, unchanged), removed (decided before, gone now).
A decided function that only moved/renamed with an identical body keeps its ID (status moved).

Heuristic and language-agnostic (JS/TS, Python, Go, Java, Kotlin, C#, PHP, Ruby, Rust, Scala).
It finds candidates; the orchestrator decides what needs a test.

Usage:
  python map_functions.py --root . [--src api/]          # scan, write the map, print a summary
  python map_functions.py --root . --diff F012            # body diff since F012 was decided
  python map_functions.py --root . --accept F001 F002     # decisions done: store hash + snapshot
  python map_functions.py --root . --skip F030 F031       # user skipped them (re-asked only if changed)
  python map_functions.py --root . --retire F040          # removed function: forget it
  python map_functions.py --root . --show F012            # print one entry
"""
import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

BRACE_LANGS = {"javascript", "typescript", "go", "java", "kotlin", "csharp", "php", "rust", "scala"}
HTTP = r"get|post|put|patch|delete|all|options|head"

# ----------------------------------------------------------------------------- function starts
FN_START = [
    re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?function\s*\*?\s*([\w$]+)\s*[<(]"),
    re.compile(r"^\s*(export\s+)?(const|let|var)\s+([\w$]+)\s*(:\s*[^=]+)?=\s*(async\s*)?(\([^)]*\)|[\w$]+)\s*(:\s*[^=]+)?=>"),
    re.compile(r"^\s*(export\s+)?(const|let|var)\s+([\w$]+)\s*=\s*(async\s+)?function\b"),
    re.compile(r"^\s*(?:exports|module\.exports)\.([\w$]+)\s*=\s*(async\s*)?(function\b|\([^)]*\)\s*=>|[\w$]+\s*=>)"),
    re.compile(r"^\s*func\s+(\([^)]*\)\s*)?([\w]+)\s*[\[(]"),
    re.compile(r"^\s*(pub(\([^)]*\))?\s+)?(async\s+)?(unsafe\s+)?fn\s+(\w+)\s*[<(]"),
    re.compile(r"^\s*((public|private|protected|internal|override|open|suspend|inline)\s+)*fun\s+(<[^>]+>\s*)?([\w.]+\.)?(\w+)\s*\("),
    re.compile(r"^\s*((public|private|protected|static|final|abstract)\s+)*function\s+&?(\w+)\s*\("),
    re.compile(r"^\s*(def)\s+(\w+)\s*[\[(:=]"),  # scala
    re.compile(r"^\s*((public|private|protected|internal|static|async|override|virtual|final|synchronized|readonly|abstract|get|set)\s+)*"
               r"([\w$<>\[\],.?]+\s+)?([\w$]+)\s*(<[^>(]*>)?\s*\([^;]*\)\s*(:\s*[\w<>\[\]|,. ?]+)?\s*(throws [\w, .]+)?\s*(\{\s*)?$"),
]
NOT_FN = re.compile(r"^\s*(\}\s*)?(if|for|foreach|while|switch|catch|return|else|do|try|with|new|typeof|await|throw|"
                    r"case|using|lock|synchronized|select|when|match|elif|until|unless|yield|delete|import|package)\b")
KEYWORD_NAMES = {"if", "for", "while", "switch", "catch", "function", "return", "constructor", "super", "this", "new"}

# ----------------------------------------------------------------------------- routes
JS_ROUTE = re.compile(r"\.(" + HTTP + r")\s*\(\s*(['\"`])(/[^'\"`]*|\*)\2", re.I)
JS_ROUTE_HANDLER_REF = re.compile(r",\s*([\w$.]+)\s*\)\s*;?\s*$")
PY_ROUTE_DEC = re.compile(r"^\s*@\s*[\w.]+\.(" + HTTP + r"|api_route|route|websocket)\s*\(\s*(?:path\s*=\s*)?[rf]?['\"]([^'\"]*)['\"]([^)]*)", re.I)
DJANGO_PATH = re.compile(r"\b(?:re_)?path\s*\(\s*r?['\"]([^'\"]*)['\"]\s*,\s*([\w.]+)")
NEST_CONTROLLER = re.compile(r"@Controller\s*\(\s*(?:\{[^}]*path\s*:\s*)?['\"]([^'\"]*)['\"]")
NEST_METHOD = re.compile(r"^\s*@(Get|Post|Put|Patch|Delete|All|Options|Head)\s*\(\s*(?:['\"]([^'\"]*)['\"])?")
SPRING_CLASS = re.compile(r"^\s*@RequestMapping\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\"", re.M)
SPRING_METHOD = re.compile(r"^\s*@(Get|Post|Put|Patch|Delete|Request)Mapping\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?\{?\s*\"([^\"]*)\")?")
ASP_CLASS = re.compile(r"^\s*\[Route\(\s*\"([^\"]*)\"", re.M)
ASP_METHOD = re.compile(r"^\s*\[Http(Get|Post|Put|Patch|Delete)(?:\(\s*\"([^\"]*)\")?")
ASP_MINIMAL = re.compile(r"\.Map(Get|Post|Put|Patch|Delete)\s*\(\s*\"([^\"]*)\"\s*,\s*([\w.]+)?")
GO_ROUTE = re.compile(r"\.(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\s*\(\s*\"([^\"]+)\"\s*,\s*([\w.]+)")
LARAVEL = re.compile(r"Route::(" + HTTP + r"|any|match)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(?:\[\s*([\w\\]+)::class\s*,\s*['\"](\w+)['\"]|['\"]([\w\\]+)@(\w+)['\"]|function)", re.I)
RAILS = re.compile(r"^\s*(" + HTTP + r")\s+['\"]([^'\"]+)['\"]\s*,\s*to:\s*['\"](\w+)#(\w+)['\"]", re.I)

BRANCH = re.compile(r"\b(if|else|elif|for|foreach|while|switch|case|catch|except|try|match|when|unless|until|rescue)\b|\?\s*[^:]+:|&&|\|\||\?\?")
MIDDLEWARE_NAME = re.compile(r"(?i)middleware|guard|interceptor|require|authenticat|authoriz|verify|ratelimit|rate_limit|limiter|protect|ensure|check(auth|role|perm)")
MIDDLEWARE_SIG = re.compile(r"\(\s*(req|request|ctx|c)\s*(:\s*\w+)?\s*,\s*(res|response|reply|next)\b.*\bnext\b|\(\s*(ctx|c)\s*,\s*next\s*\)|\bnext\s*:\s*NextFunction|call_next")
KIND_BY_PATH = [
    ("middleware", re.compile(r"(?i)(^|/)(middlewares?|guards?|interceptors?|policies)(/|\.|$)")),
    ("controller", re.compile(r"(?i)(^|/)(controllers?|handlers?|routes?|routers?|views|endpoints|resolvers?|api)(/|\.|$)|controller\.|handler\.|routes?\.|router\.|views?\.py$")),
    ("job", re.compile(r"(?i)(^|/)(jobs?|workers?|queues?|cron|tasks?|consumers?|listeners?|subscribers?)(/|\.|$)")),
    ("service", re.compile(r"(?i)(^|/)(services?|use-?cases?|usecases|domain|application|core|logic|features?)(/|\.|$)|service\.")),
    ("repository", re.compile(r"(?i)(^|/)(repositor(y|ies)|repos?|dao|models?|entities|store|stores|db|database|data)(/|\.|$)|repository\.|model\.")),
    ("util", re.compile(r"(?i)(^|/)(utils?|lib|libs|helpers?|common|shared|support)(/|\.|$)")),
]
FRONTEND_DIR = re.compile(r"(?i)(^|/)(web|frontend|client|ui|www|public|static|assets|components|pages|app/\(|mobile|ios|android)(/|$)")


# ----------------------------------------------------------------------------- helpers

def strip_strings(line):
    line = re.sub(r"""(['"`])(?:\\.|(?!\1).)*\1""", "''", line)
    if "//" in line:
        line = line.split("//")[0]
    return line


def normalize(lines, lang):
    text = "\n".join(lines)
    if lang in BRACE_LANGS:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"(?m)(^|[^:'\"])//.*$", r"\1", text)
    if lang in ("python", "ruby", "php"):
        text = re.sub(r"(?m)^\s*#.*$", "", text)
    if lang == "python":
        text = re.sub(r'(?s)^(\s*(?:async\s+)?def[^\n]*\n)\s*(\"\"\"|\'\'\').*?\2', r"\1", text, count=1)
    return re.sub(r"\s+", " ", text).strip()


def brace_end(lines, i, max_scan=6):
    """1-based end line of the {...} block opening on line i (0-based) or within max_scan lines."""
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
        if not started and (j - i >= max_scan or strip_strings(lines[j]).rstrip().endswith(";")):
            return None
    return len(lines) if started else None


def expr_end(lines, i, max_scan=12):
    """End line of an expression-bodied arrow function: until a line ending with ';' or a blank line."""
    for j in range(i, min(len(lines), i + max_scan)):
        s = strip_strings(lines[j]).rstrip()
        if s.endswith(";") or (j > i and not s.strip()):
            return j + 1 if s.strip() else j
    return i + 1


def fn_name(line):
    if NOT_FN.match(line):
        return None, None
    for idx, rx in enumerate(FN_START):
        m = rx.search(line)
        if not m:
            continue
        groups = [g for g in m.groups() if g and re.match(r"^[\w$]+$", g.strip())]
        groups = [g for g in groups if g not in ("export", "default", "async", "const", "let", "var", "function", "def",
                                                 "public", "private", "protected", "internal", "static", "override",
                                                 "final", "abstract", "pub", "unsafe", "open", "suspend", "inline",
                                                 "virtual", "synchronized", "readonly", "fun")]
        if not groups:
            return None, None
        name = (groups[-1] if idx not in (0, 1, 2) else (m.group(4) if idx == 0 else m.group(3))).strip()
        if name in KEYWORD_NAMES:
            return None, None
        return name, idx
    return None, None


# ----------------------------------------------------------------------------- per-language extraction

def brace_functions(lines, lang):
    """[(name, start, end, arrow_expr)] for brace languages. Nested functions are listed separately."""
    out = []
    n = len(lines)
    for i in range(n):
        line = lines[i]
        rm = JS_ROUTE.search(line) if lang in ("javascript", "typescript") else None
        if rm and ("=>" in line or "function" in line):
            end = brace_end(lines, i) or expr_end(lines, i)
            out.append((f"{rm.group(1).upper()} {rm.group(3)}", i + 1, end, False))
            continue
        name, idx = fn_name(line)
        if not name:
            continue
        if idx == 9 and not (line.rstrip().endswith("{") or (i + 1 < n and lines[i + 1].strip().startswith("{"))):
            continue  # a call, not a declaration
        if idx == 9 and lang in ("javascript", "typescript") and re.match(r"^\s*[\w$]+\s*\(", line) is None \
                and not re.match(r"^\s*(public|private|protected|static|async|get|set|override|readonly)\b", line):
            continue
        end = brace_end(lines, i)
        if end is None and idx in (1, 3) and "=>" in line:
            out.append((name, i + 1, expr_end(lines, i), True))
            continue
        if end is None:
            continue
        out.append((name, i + 1, end, False))
    return out


def python_functions(lines):
    out = []
    classes = []  # (indent, name)
    n = len(lines)
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        while classes and ind <= classes[-1][0]:
            classes.pop()
        cm = re.match(r"^(\s*)class\s+(\w+)", line)
        if cm:
            classes.append((len(cm.group(1)), cm.group(2)))
            continue
        m = re.match(r"^(\s*)(async\s+)?def\s+(\w+)\s*\(", line)
        if not m:
            continue
        ind = len(m.group(1))
        start = i
        while start > 0 and lines[start - 1].strip().startswith("@"):
            start -= 1
        end = i + 1
        j = i + 1
        paren = line.count("(") - line.count(")")
        while j < n:
            s = lines[j]
            paren += s.count("(") - s.count(")") if paren > 0 else 0
            if s.strip() and not s.lstrip().startswith("#") and paren <= 0:
                if len(s) - len(s.lstrip()) <= ind:
                    break
                end = j + 1
            j += 1
        qual = ".".join([c[1] for c in classes] + [m.group(3)])
        out.append((qual, start + 1, end, i + 1))
    return out


def ruby_functions(lines):
    out = []
    opener = re.compile(r"^\s*(def|class|module|if|unless|while|until|case|begin|for)\b|\bdo\s*(\|[^|]*\|)?\s*$")
    for i, line in enumerate(lines):
        m = re.match(r"^\s*def\s+(self\.)?([\w?!=]+)", line)
        if not m:
            continue
        if re.search(r"\bend\s*$", line) and line.count("def") == 1 and re.search(r"[;)]\s*\w", line):
            out.append((m.group(2), i + 1, i + 1))
            continue
        depth = 0
        for j in range(i, len(lines)):
            s = lines[j].split("#")[0]
            if opener.search(s):
                depth += 1
            if re.match(r"^\s*end\b", s):
                depth -= 1
                if depth == 0:
                    out.append((m.group(2), i + 1, j + 1))
                    break
    return out


# ----------------------------------------------------------------------------- scan one file

def scan_file(root, relpath, lang):
    text = C.read_text(os.path.join(root, relpath))
    if text is None:
        return [], []
    lines = text.splitlines()
    funcs, routes = [], []
    file_exports = set(re.findall(r"(?:module\.)?exports\.([\w$]+)\s*=", text))
    me = re.search(r"module\.exports\s*=\s*\{([^}]*)\}", text)
    if me:
        file_exports.update(re.findall(r"([\w$]+)\s*(?:[:,]|$)", me.group(1)))
    for grp in re.findall(r"export\s*\{([^}]*)\}", text):
        file_exports.update(re.findall(r"([\w$]+)(?:\s+as\s+[\w$]+)?\s*(?:,|$)", grp))

    # class-level route prefixes (Nest / Spring / ASP.NET)
    prefix = ""
    for rx in (NEST_CONTROLLER, SPRING_CLASS, ASP_CLASS):
        m = rx.search(text)
        if m:
            prefix = "/" + m.group(1).strip("/") if m.group(1) else ""
            break

    if lang in BRACE_LANGS:
        raw = brace_functions(lines, lang)
        items = [(name, s, e, s) for name, s, e, _x in raw]
    elif lang == "python":
        items = python_functions(lines)
    elif lang == "ruby":
        items = [(name, s, e, s) for name, s, e in ruby_functions(lines)]
    else:
        items = []

    seen_names = {}
    for name, start, end, decl in items:
        body = lines[start - 1:end]
        decl_line = lines[decl - 1] if decl - 1 < len(lines) else ""
        # decorators / attributes just above the declaration (Python decorators are inside start..decl)
        above = lines[max(0, start - 6):start - 1] if lang != "python" else lines[start - 1:decl - 1]
        route = None
        for a in reversed(above):
            s = a.strip()
            if s and not s.startswith(("@", "[", "//", "#", "*", "/*")):
                break  # reached the previous statement: the annotations above belong to someone else
            for rx, kind in ((PY_ROUTE_DEC, "py"), (NEST_METHOD, "nest"), (SPRING_METHOD, "spring"), (ASP_METHOD, "asp")):
                m = rx.search(a)
                if m:
                    method = m.group(1).upper()
                    path = m.group(2) or ""
                    if kind == "py":
                        if method in ("ROUTE", "API_ROUTE"):
                            mm = re.search(r"methods\s*=\s*\[([^\]]+)\]", m.group(3) or "")
                            method = ",".join(x.strip(" '\"").upper() for x in mm.group(1).split(",")) if mm else "GET"
                        elif method == "WEBSOCKET":
                            method = "WS"
                    else:
                        if method == "REQUEST":
                            method = "ANY"
                        path = (prefix.rstrip("/") + "/" + path.strip("/")).rstrip("/") or "/"
                    route = {"method": method, "path": path}
                    break
            if route:
                break
        if " " in name and re.match(r"^(GET|POST|PUT|PATCH|DELETE|ALL|OPTIONS|HEAD) ", name):
            route = {"method": name.split(" ", 1)[0], "path": name.split(" ", 1)[1]}
        n = seen_names.get(name, 0)
        seen_names[name] = n + 1
        key = f"{relpath}::{name}" + (f"#{n + 1}" if n else "")
        inner = [l for l in body[1:-1] if l.strip() and not l.strip().startswith(("//", "#", "*", "/*"))]
        branches = sum(1 for l in body if BRANCH.search(strip_strings(l)))
        exported = (
            decl_line.lstrip().startswith("export") or name in file_exports or
            (lang == "go" and name[:1].isupper()) or
            (lang in ("java", "kotlin", "csharp", "scala") and not re.search(r"\b(private|internal)\b", decl_line)) or
            (lang == "rust" and decl_line.lstrip().startswith("pub")) or
            (lang == "php" and not re.search(r"\b(private|protected)\b", decl_line)) or
            (lang == "python" and not name.split(".")[-1].startswith("_")) or
            (lang == "ruby") or route is not None
        )
        kind = "route" if route else None
        sig_text = " ".join(lines[decl - 1:decl + 2])
        if not kind and (MIDDLEWARE_SIG.search(sig_text) or (MIDDLEWARE_NAME.search(name) and re.search(r"\bnext\b", sig_text))):
            kind = "middleware"
        if not kind:
            kind = next((k for k, rx in KIND_BY_PATH if rx.search(relpath)), "other")
        funcs.append({
            "key": key, "name": name, "file": relpath, "start": start, "end": end, "lines": end - start + 1,
            "lang": lang, "kind": kind, "exported": bool(exported), "route": route,
            "trivial": len(inner) <= 3 and branches == 0, "branches": branches,
            "hash": C.sha(normalize(body, lang)),
            # same body under another name/file → a rename/move, not a new function
            "shape": C.sha(normalize(body, lang).replace(name.split(".")[-1], "§")),
        })

    # route registrations that reference a handler by name
    for i, line in enumerate(lines):
        ref = None
        m = JS_ROUTE.search(line) if lang in ("javascript", "typescript") else None
        if m and not ("=>" in line or "function" in line):
            r = JS_ROUTE_HANDLER_REF.search(line)
            ref = r.group(1) if r else None
            routes.append({"method": m.group(1).upper(), "path": m.group(3), "file": relpath, "line": i + 1, "handler_ref": ref})
            continue
        for rx, kind in ((GO_ROUTE, "go"), (ASP_MINIMAL, "asp"), (LARAVEL, "laravel"), (RAILS, "rails"), (DJANGO_PATH, "django")):
            m = rx.search(line)
            if not m:
                continue
            if kind == "go":
                method, path, ref = m.group(1).upper(), m.group(2), m.group(3)
                if method in ("HANDLEFUNC", "HANDLE"):
                    parts = path.split(" ", 1)
                    method, path = (parts[0], parts[1]) if len(parts) == 2 and parts[0].isupper() else ("ANY", path)
            elif kind == "asp":
                method, path, ref = m.group(1).upper(), m.group(2), m.group(3)
            elif kind == "laravel":
                method, path = m.group(1).upper(), m.group(2)
                ref = m.group(4) or m.group(6)
            elif kind == "rails":
                method, path, ref = m.group(1).upper(), m.group(2), m.group(4)
            else:
                method, path, ref = "ANY", "/" + m.group(1).lstrip("^/"), m.group(2)
            routes.append({"method": method, "path": path, "file": relpath, "line": i + 1, "handler_ref": ref})
            break
    for f in funcs:
        if f["route"]:
            routes.append({"method": f["route"]["method"], "path": f["route"]["path"], "file": relpath,
                           "line": f["start"], "handler_ref": None, "function_key": f["key"]})
    return funcs, routes


# ----------------------------------------------------------------------------- scan + state

def pick_src(root, given):
    if given:
        return [g.rstrip("/\\") for g in given]
    env = C.load_json(C.qa_path(root, "env.json"), {}) or {}
    if env.get("src"):
        return env["src"]
    for c in ("api", "server", "backend", "apps/api", "apps/server", "src", "app"):
        if os.path.isdir(os.path.join(root, c)):
            return [c]
    return ["."]


def scan(root, src_dirs):
    funcs, routes = [], []
    for relpath, lang in C.walk_code(root, src_dirs):
        if C.GENERATED_PATH.search(relpath):
            continue
        if src_dirs == ["."] and FRONTEND_DIR.search(relpath):
            continue
        f, r = scan_file(root, relpath, lang)
        funcs.extend(f)
        routes.extend(r)
    # link named handlers to functions
    by_name = {}
    for f in funcs:
        by_name.setdefault(f["name"].split(".")[-1], []).append(f)
    for r in routes:
        if r.get("function_key") or not r.get("handler_ref"):
            continue
        ref = re.split(r"[.#:\\]", r["handler_ref"])[-1]
        cands = by_name.get(ref, [])
        if len(cands) > 1:
            owner = r["handler_ref"].split(".")[0].lower()
            narrowed = [c for c in cands if owner and owner.replace("controller", "") in c["file"].lower()]
            cands = narrowed or cands
        if len(cands) == 1:
            r["function_key"] = cands[0]["key"]
            if not cands[0]["route"]:
                cands[0]["route"] = {"method": r["method"], "path": r["path"]}
                cands[0]["kind"] = "route"
    return funcs, routes


def assign(root, funcs):
    """Give every function a stable ID and a status against qa/state.json. Returns (state, removed)."""
    st = C.load_state(root)
    ids = st.setdefault("ids", {})
    decided = st.setdefault("functions", {})
    next_id = int(st.get("next_id", 1))
    current = {f["key"]: f for f in funcs}
    # moved/renamed: a decided key vanished and a new key has the identical body
    gone = {k: v for k, v in decided.items() if k not in current}
    by_shape = {}
    for k, v in gone.items():
        by_shape.setdefault(v.get("shape") or v.get("hash"), []).append(k)
    for f in funcs:
        if f["key"] in decided or f["key"] in ids:
            continue
        olds = by_shape.get(f["shape"]) or by_shape.get(f["hash"]) or []
        if olds:
            old = olds.pop(0)
            decided[f["key"]] = dict(decided.pop(old), moved_from=old, hash=f["hash"])
            ids[f["key"]] = ids.pop(old, decided[f["key"]].get("id"))
            f["moved_from"] = old
    for f in funcs:
        if f["key"] not in ids:
            ids[f["key"]] = f"F{next_id:03d}"
            next_id += 1
        f["id"] = ids[f["key"]]
        d = decided.get(f["key"])
        if not d:
            f["status"] = "new"
        elif d.get("hash") == f["hash"] or (f.get("moved_from") and d.get("shape") == f["shape"]):
            f["status"] = "moved" if f.get("moved_from") else ("skipped" if d.get("status") == "skipped" else "unchanged")
        else:
            f["status"] = "changed"
    removed = [{"id": v.get("id") or ids.get(k), "key": k, "status": "removed"} for k, v in decided.items() if k not in current]
    st["next_id"] = next_id
    return st, removed


def write_map(root, src_dirs, funcs, routes, removed):
    data = {"generated_at": C.now_iso(), "src": src_dirs, "functions": funcs, "removed": removed,
            "routes": routes, "unlinked_routes": [r for r in routes if not r.get("function_key")]}
    counts = {}
    for f in funcs:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    counts["removed"] = len(removed)
    data["counts"] = counts
    C.save_json(C.qa_path(root, "function-map.json"), data)
    return data


def current_body(root, f):
    text = C.read_text(os.path.join(root, f["file"])) or ""
    return text.splitlines()[f["start"] - 1:f["end"]]


def find(funcs, fid):
    return next((f for f in funcs if f["id"] == fid or f["key"] == fid), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--diff")
    ap.add_argument("--accept", nargs="*")
    ap.add_argument("--skip", nargs="*")
    ap.add_argument("--retire", nargs="*")
    ap.add_argument("--show")
    ap.add_argument("--list", choices=["new", "changed", "removed", "all"], help="print id/name/file lines for that status")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    src_dirs = pick_src(root, a.src)

    funcs, routes = scan(root, src_dirs)
    st, removed = assign(root, funcs)
    snap_dir = C.qa_path(root, "snapshots")

    if a.diff:
        f = find(funcs, a.diff)
        if not f:
            print(f"{a.diff}: not found in the current code (removed?)")
            return 1
        old = C.read_text(os.path.join(snap_dir, f"{f['id']}.txt"))
        if old is None:
            print(f"{f['id']}: no snapshot (never accepted), nothing to diff")
            return 1
        new = current_body(root, f)
        diff = list(difflib.unified_diff(old.splitlines(), new, f"{f['id']} when decided", f"{f['id']} now ({f['file']}:{f['start']})", lineterm=""))
        print("\n".join(diff) if diff else "only whitespace/comments changed")
        C.save_state(root, st)
        return 0

    if a.accept is not None or a.skip is not None or a.retire is not None:
        done = []
        for ids, status in ((a.accept or [], "decided"), (a.skip or [], "skipped")):
            for fid in ids:
                f = find(funcs, fid)
                if not f:
                    print(f"{fid}: not found, skipped")
                    continue
                st["functions"][f["key"]] = {"id": f["id"], "hash": f["hash"], "shape": f["shape"], "status": status,
                                             "at": C.now_iso()}
                os.makedirs(snap_dir, exist_ok=True)
                with open(os.path.join(snap_dir, f"{f['id']}.txt"), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(current_body(root, f)) + "\n")
                f["status"] = "skipped" if status == "skipped" else "unchanged"
                done.append(f"{f['id']} {status}")
        for fid in a.retire or []:
            key = next((k for k, v in st["functions"].items() if v.get("id") == fid or k == fid), None)
            if key:
                st["functions"].pop(key)
                st["ids"].pop(key, None)
                removed = [r for r in removed if r["key"] != key]
                done.append(f"{fid} retired")
            else:
                print(f"{fid}: not in state, skipped")
        C.save_state(root, st)
        write_map(root, src_dirs, funcs, routes, removed)
        print("ok: " + ", ".join(done) if done else "nothing changed")
        return 0

    C.save_state(root, st)
    data = write_map(root, src_dirs, funcs, routes, removed)

    if a.show:
        f = find(funcs, a.show)
        print(f if f else f"{a.show}: not found")
        return 0 if f else 1

    kinds = {}
    for f in funcs:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    c = data["counts"]
    print(f"src: {', '.join(src_dirs)} · functions: {len(funcs)} · routes: {len(routes)} "
          f"(unlinked: {len(data['unlinked_routes'])}) · trivial: {sum(1 for f in funcs if f['trivial'])}")
    print("status: " + " · ".join(f"{k} {v}" for k, v in sorted(c.items())))
    print("kinds: " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
    want = a.list
    for f in funcs:
        if f["status"] == "changed" or (want in ("all", f["status"])):
            r = f" [{f['route']['method']} {f['route']['path']}]" if f["route"] else ""
            print(f"  {f['status']:<9} {f['id']} {f['name']}{r} {f['file']}:{f['start']}-{f['end']}")
    for r in removed:
        print(f"  removed   {r['id']} {r['key']}")
    print("written: qa/function-map.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
