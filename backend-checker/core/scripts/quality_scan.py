"""Cheap static candidates for the code-quality agent (sections 4, 5, 6, 10 and 2).

- long functions (> --fn-lines), long files (> --file-lines), deep nesting (> --max-depth)
  Python via `ast`; brace languages via a brace/keyword heuristic.
- magic numbers (repeated or unexplained numeric literals) and repeated string literals
- unused exports / top-level functions (name never mentioned in another file), unused dependencies
- commented-out code blocks
- weak types (`any`, untyped `dict`/`Any` parameters)
Candidates only: the agent confirms each one before reporting it.

Usage: python quality_scan.py --root . [--plan docs/.backend-checks/plan-code-quality.json]
Writes docs/.backend-checks/quality-candidates.json and prints counts.
"""
import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

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
NUM = re.compile(r"(?<![\w.$])-?\d+\.\d+|(?<![\w.$])\d{2,}(?![\w.])")
OK_NUMS = {"10", "100", "1000", "200", "201", "204", "301", "302", "304", "400", "401", "403", "404", "405", "409", "410", "422",
           "429", "500", "502", "503", "0.0", "1.0", "0.5", "24", "60", "12", "16", "32", "64", "1024", "8", "2", "3"}
CONST_DECL = re.compile(r"^\s*(export\s+)?(const|final|static|public static final|readonly)?\s*[A-Z][A-Z0-9_]{2,}\s*[:=]|^\s*[A-Z][A-Z0-9_]{2,}\s*=|enum\s|^\s*#\s*define")
STRLIT = re.compile(r"""(['"])([A-Za-z][\w\- ]{2,40})\1""")
SKIP_LINE = re.compile(r"^\s*(import|from\s+\S+\s+import|require|#|//|\*|/\*)|require\(|console\.|logger\.|logging\.|print\(|\.(get|post|put|patch|delete|use)\(\s*['\"]|@\w+\.(get|post|put|patch|delete)\(")
COMMENTED_CODE = re.compile(r"^\s*(//|#)\s*.*([;{}()=]|\breturn\b|\bdef\b|\bconst\b|\bimport\b)")
JS_EXPORT = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:const|let|var|function\*?|class|type|interface|enum)\s+([\w$]+)")
JS_EXPORT_LIST = re.compile(r"(?:module\.exports\s*=\s*\{|export\s*\{)([^}]*)\}")
JS_EXPORTS_DOT = re.compile(r"^\s*(?:module\.)?exports\.([\w$]+)\s*=")
ANY_TS = re.compile(r":\s*any\b|\bas\s+any\b|<any>|any\[\]")
PY_WEAK = re.compile(r"def\s+\w+\(([^)]*)\)")
DEV_TOOLS = re.compile(r"^(@types/|typescript$|ts-node|tsx$|eslint|prettier|nodemon|jest|vitest|mocha|chai|supertest|husky|lint-staged|@swc/|"
                       r"@babel/|babel-|webpack|vite|rollup|esbuild|concurrently|cross-env|dotenv-cli|rimraf|tsc-alias|tsconfig-paths|prisma$)")
PY_IMPORT_ALIAS = {"pyjwt": "jwt", "python-jose": "jose", "beautifulsoup4": "bs4", "pyyaml": "yaml", "python-multipart": "multipart",
                   "pillow": "PIL", "psycopg2-binary": "psycopg2", "python-dotenv": "dotenv", "scikit-learn": "sklearn",
                   "uvicorn": None, "gunicorn": None, "pytest": None, "python-multipart*": None}


def top_level_names(body):
    """Exported names in `{ a, b: c, d: (x) => y }`: the key of each entry at depth 0."""
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    out = []
    for part in parts:
        m = re.match(r"\s*([\w$]+)", part)
        if m:
            out.append(m.group(1))
    return out


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


class PyVisitor(ast.NodeVisitor):
    NEST = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith) + ((ast.Match,) if hasattr(ast, "Match") else ())

    def __init__(self):
        self.funcs = []

    def depth(self, node, d=0):
        best = d
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            nd = d + 1 if isinstance(ch, self.NEST) else d
            best = max(best, self.depth(ch, nd))
        return best

    def visit_FunctionDef(self, node):
        self.funcs.append((node.name, node.lineno, getattr(node, "end_lineno", node.lineno), self.depth(node),
                           [d.attr if isinstance(d, ast.Attribute) else getattr(getattr(d, "func", None), "attr", "") for d in node.decorator_list]))
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    ap.add_argument("--fn-lines", type=int, default=50)
    ap.add_argument("--file-lines", type=int, default=400)
    ap.add_argument("--max-depth", type=int, default=3)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"))
    plan = C.load_json(a.plan) if a.plan else None
    focus = {f["path"] for f in plan["files_to_analyze"]} if plan and plan.get("mode") == "incremental" else None

    texts = {}
    for p, m in index["files"].items():
        if m["lang"] in ("config", "sql", "prisma", "graphql"):
            continue
        t, _ = C.read_text(os.path.join(root, p))
        if t is not None:
            texts[p] = t
    extra_texts = {}
    for p, m in index.get("extra_files", {}).items():
        if m["lang"] in C.CODE_EXTS.values():
            t, _ = C.read_text(os.path.join(root, p))
            if t is not None:
                extra_texts[p] = t

    res = {"thresholds": {"function_lines": a.fn_lines, "file_lines": a.file_lines, "nesting": a.max_depth},
           "long_files": [], "long_functions": [], "deep_nesting": [], "magic_numbers": [], "repeated_strings": [],
           "unused_exports": [], "unused_dependencies": [], "commented_out_code": [], "weak_types": []}
    num_hits, str_hits = {}, {}
    exports = []
    for p, text in texts.items():
        meta = index["files"][p]
        if meta.get("test"):
            continue
        lines = text.splitlines()
        if len(lines) > a.file_lines:
            res["long_files"].append({"file": p, "lines": len(lines)})
        funcs = []
        if meta["lang"] == "python":
            try:
                v = PyVisitor()
                v.visit(ast.parse(text))
                funcs = [(n, s, e, d) for n, s, e, d, _ in v.funcs]
                decorated = {n for n, s, e, d, decs in v.funcs if any(decs)}
                tree = ast.parse(text)
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name not in decorated \
                            and not node.name.startswith("_"):
                        exports.append((p, node.lineno, node.name, "inline"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = node.args.args
                        defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
                        weak = []
                        for arg, dflt in zip(args, defaults):
                            if arg.arg in ("self", "cls"):
                                continue
                            ann = arg.annotation
                            loose = isinstance(ann, ast.Name) and ann.id in ("dict", "Any", "object", "list")
                            untyped = ann is None and not isinstance(dflt, ast.Call)  # `db=Depends(...)` is DI, not data
                            if loose or untyped:
                                weak.append(arg.arg + (": " + ann.id if loose else ""))
                        if weak:
                            res["weak_types"].append({"file": p, "line": node.lineno, "function": node.name, "params": weak[:6]})
            except SyntaxError:
                pass
        elif meta["lang"] in BRACE_LANGS:
            funcs = brace_functions(lines)
            for i, line in enumerate(lines, 1):
                m = JS_EXPORT.match(line)
                if m:
                    exports.append((p, i, m.group(1), "inline"))
                m = JS_EXPORTS_DOT.match(line)
                if m:
                    exports.append((p, i, m.group(1), "list"))
            for m in JS_EXPORT_LIST.finditer(text):
                ln = text[:m.start()].count("\n") + 1
                for name in top_level_names(m.group(1)):
                    exports.append((p, ln, name, "list"))
            if meta["lang"] == "typescript":
                c = len(ANY_TS.findall(text))
                if c:
                    res["weak_types"].append({"file": p, "any_count": c})
        for name, s, e, d in funcs:
            if e - s + 1 > a.fn_lines:
                res["long_functions"].append({"file": p, "line": s, "end": e, "name": name, "lines": e - s + 1})
            if d > a.max_depth:
                res["deep_nesting"].append({"file": p, "line": s, "name": name, "depth": d})
        run = []
        for i, line in enumerate(lines + [""], 1):
            if COMMENTED_CODE.match(line):
                run.append(i)
                continue
            if len(run) >= 3:
                res["commented_out_code"].append({"file": p, "start": run[0], "end": run[-1]})
            run = []
        for i, line in enumerate(lines, 1):
            if SKIP_LINE.search(line) or CONST_DECL.search(line):
                continue
            code = re.sub(r"""(['"`])(?:\\.|(?!\1).)*\1""", "''", line)
            for m in NUM.finditer(code):
                v = m.group(0).lstrip("-")
                if v not in OK_NUMS and f"{p}:{i}" not in num_hits.get(v, []):
                    num_hits.setdefault(v, []).append(f"{p}:{i}")
            for m in STRLIT.finditer(line):
                s = m.group(2)
                if not re.search(r"\s{2,}|^(utf-?8|json|id|GET|POST|PUT|DELETE|PATCH|true|false|none|null)$", s, re.I):
                    str_hits.setdefault(s, []).append(f"{p}:{i}")

    for v, locs in sorted(num_hits.items(), key=lambda kv: -len(kv[1])):
        res["magic_numbers"].append({"value": v, "count": len(locs), "locations": locs[:8]})
    res["magic_numbers"] = res["magic_numbers"][:60]
    for s, locs in sorted(str_hits.items(), key=lambda kv: -len(kv[1])):
        if len(locs) >= 3:
            res["repeated_strings"].append({"value": s, "count": len(locs), "locations": locs[:8]})
    res["repeated_strings"] = res["repeated_strings"][:40]

    corpus = {p: t for p, t in {**texts, **extra_texts}.items()}
    seen_exp = set()
    for p, line, name, how in exports:
        if len(name) < 3 or name in ("default", "router", "app", "main", "handler", "config", "module") or (p, name) in seen_exp:
            continue
        seen_exp.add((p, name))
        rx = re.compile(r"\b" + re.escape(name) + r"\b")
        used_elsewhere = any(rx.search(t) for q, t in corpus.items() if q != p)
        used_here = len(rx.findall(corpus[p])) > (2 if how == "list" else 1)  # definition (+ export list entry)
        if not used_elsewhere and not used_here:
            res["unused_exports"].append({"file": p, "line": line, "name": name})
        elif not used_elsewhere and index["files"][p]["lang"] != "python":
            res["unused_exports"].append({"file": p, "line": line, "name": name, "note": "used only inside its own file; the export may be unnecessary"})

    all_code = "\n".join(texts.values())
    for d in index.get("dependencies", []):
        if not d.get("direct") or d.get("dev") or d.get("ecosystem") not in ("npm", "PyPI"):
            continue
        name = d["name"]
        if d["ecosystem"] == "npm":
            if DEV_TOOLS.match(name):
                continue
            used = re.search(r"""(require\(|from\s+|import\s*\(|import\s+)['"]""" + re.escape(name) + r"""(['"/])""", all_code)
        else:
            mod = PY_IMPORT_ALIAS.get(name.lower(), name.lower().replace("-", "_"))
            if mod is None:
                continue
            used = re.search(r"^\s*(import|from)\s+" + re.escape(mod) + r"\b", all_code, re.M | re.I)
        if not used:
            res["unused_dependencies"].append({"name": name, "version": d["version"], "manifest": d.get("manifest")})

    if focus is not None:
        def keep(item):
            f = item.get("file")
            return f is None or f in focus
        for k in ("long_files", "long_functions", "deep_nesting", "commented_out_code", "weak_types"):
            res[k] = [x for x in res[k] if keep(x)]
        for k in ("magic_numbers", "repeated_strings"):
            res[k] = [x for x in res[k] if any(l.split(":")[0] in focus for l in x["locations"])]

    C.save_json(C.state_path(root, "quality-candidates.json"), res)
    print(json.dumps({"candidates_json": f"{C.STATE_DIR}/quality-candidates.json".replace("\\", "/"),
                      **{k: len(v) for k, v in res.items() if isinstance(v, list)}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
