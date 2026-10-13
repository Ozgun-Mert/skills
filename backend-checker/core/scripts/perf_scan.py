"""Cheap static candidates for the performance agent (no LLM involved).

Finds lines worth a look for:
  query_in_loop, write_in_loop, http_in_loop, await_in_loop     (SQL 1, external APIs 11, async 8)
  membership_in_loop, sort_in_loop, nested_loops, handwritten_sort,
  recursion_no_memo, string_concat_in_loop, pop_front_in_loop    (complexity 2)
  select_star, unbounded_query                                   (SQL 1, pagination 7)
  blocking_in_async, sync_io_in_handler                          (async 8)
  client_per_call, http_no_timeout                               (pooling & timeouts 9)
  unbounded_module_cache, whole_file_read                        (memory 10)
  uncached_get_routes                                            (caching 3)
  startup_work                                                   (cold start 13)
plus `infra` facts (compression middleware, app-served static files, cache libraries).
Candidates only: the agent confirms each one in the code before reporting it.

Usage: python perf_scan.py --root . [--plan docs/.backend-checks/plan-performance.json]
Writes docs/.backend-checks/perf-candidates.json and prints counts.
"""
import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
from common import BRACE_LANGS, brace_block_end, brace_functions  # noqa: E402
from index import HOT  # noqa: E402  (same hotspot patterns the index uses)

CAP = 60
DB_RX = HOT["db"]
HTTP_RX = re.compile(r"\b(fetch|axios(\.\w+)?|got|superagent|request|needle|ky)\s*\(|\bhttp[s]?\.(get|request)\(|\brequests\.(get|post|put|patch|delete|head|request)\(|"
                     r"\bhttpx\.(get|post|put|patch|delete|request)\(|urlopen\(|\bclient\.(get|post|put|patch|delete)\(|http\.(Get|Post|NewRequest)\(|RestTemplate|WebClient")
WRITE_RX = re.compile(r"(?i)\b(insert|update|delete|upsert|save|create|destroy|bulk\w*|commit|add)\w*\s*\(|\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b")
MEMBER_RX = re.compile(r"\.(includes|indexOf|lastIndexOf|find|findIndex|some|filter|contains|Contains|IndexOf)\s*\(|\bin_array\(|\bArrays\.asList\(")
SORT_RX = re.compile(r"\.(sort|sorted|toSorted|OrderBy|sortBy)\s*\(|\bsorted\(|\bsort\.(Slice|Sort|Strings|Ints)\(|usort\(|Collections\.sort\(")
SELECT_STAR = re.compile(r"(?i)\bselect\s+\*\s+from\b|\bselect\s+\w+\.\*\s+from\b")
UNBOUNDED_RX = re.compile(r"\.findMany\(\s*\)|\.findMany\(\s*\{(?![^}]*\b(take|first|cursor)\b)[^}]*\}\s*\)|\.findAll\(\s*\)|\.find\(\s*(\{\s*\})?\s*\)(?!\s*\.\s*limit)|"
                          r"\.objects\.all\(\)(?!\s*\[)|\.fetchall\(\)|\.all\(\)\s*$|\.all\(\)\s*[),;]|"
                          r"(?i:select\s+[\w*.,\s]+\s+from\s+\w+\s*['\"`])")
CLIENT_RX = re.compile(r"new\s+(Pool|Client|PrismaClient|Redis|IORedis|MongoClient|Sequelize|Stripe|S3Client|Kafka|Queue)\s*\(|\bcreate(Client|Pool|Connection|Transport)\s*\(|"
                       r"\bmysql2?\.create\w*\(|\bknex\(\s*\{|\bcreate_engine\(|\bsessionmaker\(|\bredis\.(Redis|StrictRedis)\(|\bRedis\(|\bsmtplib\.SMTP\w*\(|"
                       r"\bboto3\.(client|resource)\(|\bMongoClient\(|\bpsycopg2?\.connect\(|\basyncpg\.(connect|create_pool)\(|\brequests\.Session\(\)|"
                       r"\bhttpx\.(Async)?Client\(|\bStripeClient\(|\bsql\.Open\(|\bDriverManager\.getConnection\(")
TIMEOUT_RX = re.compile(r"(?i)timeout|signal\s*:|AbortSignal|deadline|context\.WithTimeout")
SYNC_IO_RX = re.compile(r"\b\w+Sync\s*\(|\bexecSync\(|\bspawnSync\(|while\s*\(\s*Date\.now\(\)")
STARTUP_RX = re.compile(r"(?i)\b(load_model|joblib\.load|pickle\.load|torch\.load|tf\.keras\.models\.load|from_pretrained|read_csv|readFileSync|create_all|"
                        r"sync\(\s*\{?\s*(force|alter)|migrate|seed|warm|preload|requests\.get|urlopen|fetch\()")
COMPRESSION_RX = re.compile(r"(?i)\bcompression\s*\(|GZipMiddleware|GZip\b|brotli|@fastify/compress|gzip\s+on|compress\s*:\s*true|UseResponseCompression|Compress\(\)")
STATIC_RX = re.compile(r"express\.static\(|StaticFiles\(|serve-static|@fastify/static|res\.sendFile\(|send_file\(|FileResponse\(|static_folder|STATIC_ROOT|http\.FileServer\(")
CACHE_LIB_RX = re.compile(r"(?i)\b(redis|ioredis|memcache\w*|node-cache|lru-cache|cachetools|lru_cache|functools\.cache|django\.core\.cache|"
                          r"@cache\w*|cache_page|Cacheable|apicache|keyv|flask_caching|aiocache|fastapi_cache)\b")
GET_ROUTE_RX = re.compile(r"\.(get)\s*\(\s*['\"`]|@(app|router|api|bp)\.get\(|@Get\(|@GetMapping|Route::get\(|\[HttpGet|\.MapGet\(|\bGET\s*\(|r\.GET\(|e\.GET\(")
WRITE_SQL = re.compile(r"(?i)\b(insert\s+into|update\s+\w+\s+set|delete\s+from|upsert|merge\s+into)\b")
LOOP_RX = re.compile(r"^\s*(for|while|foreach)\s*[\s(]|\bfor\s+\w+\s*(:=|,|\s+in\s)|"
                     r"\.(forEach|map|flatMap|reduce|each|filter|find|findIndex|some|every)\s*\(\s*(async\s*)?(\(|\w+\s*=>|function)|"
                     r"\bfor\s+\w+\s+of\b|\bfor\s*\(|\bfor\s+_?\w*\s*:?=\s*range\b")


def add(res, cat, item):
    """One entry per (category, file, line): chained calls on one line are one candidate."""
    lst = res.setdefault(cat, [])
    if len(lst) < CAP and not any(x["file"] == item["file"] and x["line"] == item["line"] for x in lst):
        lst.append(item)

# --------------------------------------------------------------------------- Python (ast)

PY_DB_ATTR = {"query", "execute", "executemany", "filter", "filter_by", "get", "first", "one", "all", "scalar", "scalars", "fetchall",
              "fetchone", "fetchmany", "add", "add_all", "commit", "flush", "merge", "delete", "find", "find_one", "insert_one",
              "insert_many", "update_one", "update_many", "delete_one", "delete_many", "aggregate", "count_documents", "save",
              "create", "update", "bulk_create", "bulk_update", "select_related", "prefetch_related", "values", "raw"}
PY_DB_RECV = re.compile(r"\b(db|session|cursor|cur|conn|connection|engine|collection|coll|\w*objects|\w*repo\w*|\w*Session|tx|txn)\b")
PY_HTTP = re.compile(r"^(requests|httpx|aiohttp|urllib\.request|session|client|http)\.")
PY_BLOCKING = re.compile(r"^(requests\.\w+|time\.sleep|open|urllib\.request\.urlopen|subprocess\.\w+|smtplib\.SMTP\w*|psycopg2\.connect|socket\.\w+)$")
PY_CLIENT = re.compile(r"^(create_engine|sessionmaker|redis\.Redis|redis\.StrictRedis|Redis|smtplib\.SMTP\w*|boto3\.client|boto3\.resource|MongoClient|"
                       r"psycopg2\.connect|asyncpg\.connect|asyncpg\.create_pool|requests\.Session|httpx\.Client|httpx\.AsyncClient|"
                       r"stripe\.StripeClient|StripeClient|pymongo\.MongoClient)$")
PY_STARTUP = re.compile(r"(load_model|joblib\.load|pickle\.load|torch\.load|from_pretrained|read_csv|create_all|requests\.get|urlopen)$")


def call_name(node):
    try:
        return ast.unparse(node.func)
    except Exception:  # noqa: BLE001
        return ""


def is_db_call(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in PY_DB_ATTR:
        return False
    return bool(PY_DB_RECV.search(call_name(node))) or node.func.attr in ("execute", "executemany", "fetchall", "query", "commit")


def walk_no_defs(node):
    """ast.walk that does not descend into nested function/class definitions."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(n))


def scan_python(p, text, res):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    loops = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    module_mutables = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            val = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            mutable = isinstance(val, (ast.Dict, ast.List, ast.Set)) or (isinstance(val, ast.Call) and call_name(val) in ("dict", "list", "set", "defaultdict", "OrderedDict"))
            for t in targets:
                if isinstance(t, ast.Name) and mutable:
                    module_mutables[t.id] = node.lineno
            if isinstance(val, ast.Call) and PY_STARTUP.search(call_name(val)):
                add(res, "startup_work", {"file": p, "line": node.lineno, "detail": call_name(val)})
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and PY_STARTUP.search(call_name(node.value)):
            add(res, "startup_work", {"file": p, "line": node.lineno, "detail": call_name(node.value)})

    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        is_async = isinstance(fn, ast.AsyncFunctionDef)
        decos = " ".join(ast.unparse(d) for d in fn.decorator_list)
        memo = re.search(r"cache|memo", decos)
        self_calls = 0
        awaited = {id(n.value) for n in walk_no_defs(fn) if isinstance(n, ast.Await)}
        for n in walk_no_defs(fn):
            if isinstance(n, ast.Call):
                name = call_name(n)
                if name == fn.name:
                    self_calls += 1
                if PY_CLIENT.match(name):
                    add(res, "client_per_call", {"file": p, "line": n.lineno, "function": fn.name, "detail": name})
                if re.match(r"^(requests|httpx)\.(get|post|put|patch|delete|head|request)$", name) and not any(k.arg == "timeout" for k in n.keywords):
                    add(res, "http_no_timeout", {"file": p, "line": n.lineno, "detail": name})
                if is_async and id(n) not in awaited and (PY_BLOCKING.match(name) or is_db_call(n)):
                    add(res, "blocking_in_async", {"file": p, "line": n.lineno, "function": fn.name, "detail": name})
                if isinstance(n.func, ast.Attribute) and n.func.attr in ("all", "fetchall") and ".limit(" not in name:
                    add(res, "unbounded_query", {"file": p, "line": n.lineno, "detail": name[:80]})
                if name in ("json.load", "pickle.load") or (isinstance(n.func, ast.Attribute) and n.func.attr in ("read", "readlines")
                                                              and "open(" in name):
                    add(res, "whole_file_read", {"file": p, "line": n.lineno, "detail": name[:80]})
            if isinstance(n, (ast.Assign, ast.AugAssign)):
                tgt = n.targets[0] if isinstance(n, ast.Assign) else n.target
                if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name) and tgt.value.id in module_mutables:
                    add(res, "unbounded_module_cache", {"file": p, "line": n.lineno, "name": tgt.value.id, "defined_at": module_mutables[tgt.value.id]})
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                    and n.func.value.id in module_mutables and n.func.attr in ("append", "add", "setdefault", "update", "extend"):
                add(res, "unbounded_module_cache", {"file": p, "line": n.lineno, "name": n.func.value.id, "defined_at": module_mutables[n.func.value.id]})
        if self_calls >= 2 and not memo:
            add(res, "recursion_no_memo", {"file": p, "line": fn.lineno, "function": fn.name, "self_calls": self_calls})

    for loop in [n for n in ast.walk(tree) if isinstance(n, loops)]:
        inner_loops = [n for n in walk_no_defs(loop) if isinstance(n, (ast.For, ast.AsyncFor, ast.While))]
        if inner_loops and isinstance(loop, (ast.For, ast.AsyncFor, ast.While)):
            add(res, "nested_loops", {"file": p, "line": loop.lineno, "inner_line": inner_loops[0].lineno})
            if any(isinstance(a, ast.Assign) and isinstance(a.targets[0], ast.Tuple) and len(a.targets[0].elts) == 2
                   and all(isinstance(e, ast.Subscript) for e in a.targets[0].elts) for a in walk_no_defs(loop)):
                add(res, "handwritten_sort", {"file": p, "line": loop.lineno, "detail": "nested loops with an element swap"})
        for n in walk_no_defs(loop):
            if isinstance(n, ast.Await) and isinstance(loop, (ast.For, ast.AsyncFor, ast.While)):
                add(res, "await_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno})
            if isinstance(n, ast.Call):
                name = call_name(n)
                if is_db_call(n):
                    sql = ast.unparse(n.args[0]) if n.args else ""
                    is_write = n.func.attr in ("add", "commit", "save", "create", "update", "delete", "insert_one", "update_one",
                                               "delete_one", "merge", "flush", "bulk_create", "bulk_update") or \
                        (n.func.attr in ("execute", "executemany") and bool(WRITE_SQL.search(sql)))
                    cat = "write_in_loop" if is_write else "query_in_loop"
                    add(res, cat, {"file": p, "line": n.lineno, "loop_line": loop.lineno, "detail": name[:80]})
                elif PY_HTTP.match(name):
                    add(res, "http_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno, "detail": name[:80]})
                if name in ("sorted",) or (isinstance(n.func, ast.Attribute) and n.func.attr == "sort"):
                    add(res, "sort_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno})
                if isinstance(n.func, ast.Attribute) and n.func.attr in ("index", "count", "remove"):
                    add(res, "membership_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno, "detail": name[:60]})
                if isinstance(n.func, ast.Attribute) and n.func.attr in ("pop", "insert") and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 0:
                    add(res, "pop_front_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno})
            if isinstance(n, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops) \
                    and all(isinstance(c, (ast.Name, ast.Attribute)) for c in n.comparators):
                add(res, "membership_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno, "detail": ast.unparse(n)[:60]})
            if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add) and isinstance(n.value, (ast.JoinedStr, ast.Constant)) \
                    and isinstance(getattr(n.value, "value", ""), str):
                add(res, "string_concat_in_loop", {"file": p, "line": n.lineno, "loop_line": loop.lineno})

    route_fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and any(re.search(r"\.get\(|Get\(", ast.unparse(d)) for d in n.decorator_list)]
    for fn in route_fns:
        if any(is_db_call(n) for n in walk_no_defs(fn) if isinstance(n, ast.Call)):
            add(res, "uncached_get_routes", {"file": p, "line": fn.lineno, "function": fn.name})

# --------------------------------------------------------------------------- brace languages (regex + block spans)


def scan_brace(p, text, res):
    lines = text.splitlines()
    n = len(lines)
    has_timeout_default = bool(re.search(r"axios\.create\([^)]*timeout|axios\.defaults\.timeout|timeout\s*:", text))
    fn_spans = [(s, e, name) for name, s, e, _ in brace_functions(lines)]

    def inside_function(ln):
        return any(s < ln <= e for s, e, _ in fn_spans)

    # loops
    loop_spans = []
    for i, line in enumerate(lines):
        if not LOOP_RX.search(line) or line.strip().startswith(("//", "*")):
            continue
        end = brace_block_end(lines, i, max_scan=2) or (i + 1)
        loop_spans.append((i + 1, end))
    for (s, e) in loop_spans:
        nested = [(s2, e2) for (s2, e2) in loop_spans if s < s2 <= e]
        if nested:
            add(res, "nested_loops", {"file": p, "line": s, "inner_line": nested[0][0]})
            body = "\n".join(lines[s - 1:e])
            if re.search(r"\[\s*(\w+)\[[^\]]+\]\s*,\s*\1\[[^\]]+\]\s*\]\s*=\s*\[", body) or \
                    re.search(r"(\w+)\s*=\s*(\w+)\[([^\]]+)\];?\s*\n\s*\2\[\3\]\s*=\s*\2\[", body):
                add(res, "handwritten_sort", {"file": p, "line": s, "detail": "nested loops with an element swap"})
        promise_all = any("Promise.all" in lines[k] for k in range(max(0, s - 3), s))
        for ln in range(s, e + 1):
            line = lines[ln - 1]
            if DB_RX.search(line):
                add(res, "write_in_loop" if WRITE_RX.search(line) else "query_in_loop", {"file": p, "line": ln, "loop_line": s, "detail": line.strip()[:90]})
            elif HTTP_RX.search(line):
                add(res, "http_in_loop", {"file": p, "line": ln, "loop_line": s, "detail": line.strip()[:90]})
            if re.search(r"\bawait\b", line) and not promise_all and ln != s:
                add(res, "await_in_loop", {"file": p, "line": ln, "loop_line": s})
            # On the loop's own line only look after the loop start: `.filter(p => ids.includes(p.id))` is O(n·m).
            body_part = line[LOOP_RX.search(line).end():] if ln == s and LOOP_RX.search(line) else line
            if MEMBER_RX.search(body_part):
                add(res, "membership_in_loop", {"file": p, "line": ln, "loop_line": s, "detail": line.strip()[:80]})
            if SORT_RX.search(body_part) and ln != s:
                add(res, "sort_in_loop", {"file": p, "line": ln, "loop_line": s})
            if re.search(r"\.shift\(\)|\.unshift\(|\.splice\(\s*0\s*,", line):
                add(res, "pop_front_in_loop", {"file": p, "line": ln, "loop_line": s})
            if re.search(r"\b\w+\s*\+=\s*['\"`]", line):
                add(res, "string_concat_in_loop", {"file": p, "line": ln, "loop_line": s})

    module_mutables = {}
    for i, line in enumerate(lines, 1):
        m = re.match(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(new Map\(\)|new Set\(\)|\{\s*\}|\[\s*\])\s*;?\s*$", line)
        if m:
            module_mutables[m.group(1)] = i
        if SELECT_STAR.search(line):
            add(res, "select_star", {"file": p, "line": i, "detail": line.strip()[:90]})
        if UNBOUNDED_RX.search(line):
            add(res, "unbounded_query", {"file": p, "line": i, "detail": line.strip()[:90]})
        if CLIENT_RX.search(line) and inside_function(i):
            add(res, "client_per_call", {"file": p, "line": i, "detail": line.strip()[:90]})
        if HTTP_RX.search(line) and not has_timeout_default and re.search(r"\b(fetch|axios|got|http\.Get)\b", line):
            window = "\n".join(lines[i - 1:min(n, i + 4)])
            if not TIMEOUT_RX.search(window):
                add(res, "http_no_timeout", {"file": p, "line": i, "detail": line.strip()[:90]})
        if SYNC_IO_RX.search(line) and inside_function(i):
            add(res, "sync_io_in_handler", {"file": p, "line": i, "detail": line.strip()[:90]})
        if re.search(r"readFileSync\(|readFile\(|\.readAll\(|ReadAllBytes\(|ioutil\.ReadAll\(", line) and inside_function(i):
            add(res, "whole_file_read", {"file": p, "line": i, "detail": line.strip()[:90]})
        stripped = line.strip()
        top_level = not inside_function(i) and not stripped.startswith(("import", "//", "*", "#")) and "require(" not in line
        if top_level and (re.match(r"^(await\s|\w+Sync\()", stripped) or STARTUP_RX.search(line)):
            add(res, "startup_work", {"file": p, "line": i, "detail": stripped[:90]})
    for name, at in module_mutables.items():
        rx = re.compile(r"\b" + re.escape(name) + r"\s*(\.set\(|\.add\(|\.push\(|\[[^\]]+\]\s*=)")
        for i, line in enumerate(lines, 1):
            if rx.search(line) and inside_function(i):
                add(res, "unbounded_module_cache", {"file": p, "line": i, "name": name, "defined_at": at})
                break
    for s, e, name in fn_spans:
        body = lines[s - 1:e]
        own = sum(len(re.findall(r"\b" + re.escape(name) + r"\s*\(", l)) for l in body[1:]) if re.match(r"^[\w$]+$", name) else 0
        if own >= 2 and not re.search(r"memo|cache", "\n".join(body), re.I):
            add(res, "recursion_no_memo", {"file": p, "line": s, "function": name, "self_calls": own})
        if GET_ROUTE_RX.search(lines[s - 1]) and any(DB_RX.search(l) for l in body):
            add(res, "uncached_get_routes", {"file": p, "line": s, "detail": lines[s - 1].strip()[:90]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    index = C.load_json(C.state_path(root, "index.json"))
    if not index:
        print(json.dumps({"error": "run index.py first"}))
        return 2
    plan = C.load_json(a.plan) if a.plan else None
    focus = {f["path"] for f in plan["files_to_analyze"]} if plan and plan.get("mode") == "incremental" else None

    res, infra = {}, {"compression": [], "static_served_by_app": [], "cache_libraries": []}
    all_text = []
    for p, m in index["files"].items():
        if m.get("test") or m["lang"] in ("sql", "prisma", "graphql"):
            continue
        text, _ = C.read_text(os.path.join(root, p))
        if text is None:
            continue
        if m["lang"] != "config":  # a REDIS_URL in an env example is not a cache used by the code
            all_text.append(text)
        for i, line in enumerate(text.splitlines(), 1):
            if COMPRESSION_RX.search(line):
                infra["compression"].append(f"{p}:{i}")
            if STATIC_RX.search(line):
                infra["static_served_by_app"].append(f"{p}:{i}")
        if m["lang"] == "config" or (focus is not None and p not in focus):
            continue
        if m["lang"] == "python":
            scan_python(p, text, res)
        elif m["lang"] in BRACE_LANGS:
            scan_brace(p, text, res)
    deps = {d["name"].lower() for d in index.get("dependencies", []) if d.get("name")}
    infra["cache_libraries"] = sorted({m.group(0).lower() for t in all_text for m in CACHE_LIB_RX.finditer(t)} |
                                      {d for d in deps if CACHE_LIB_RX.fullmatch(d)})
    infra["compression"] = infra["compression"][:10]
    infra["static_served_by_app"] = infra["static_served_by_app"][:10]
    if infra["cache_libraries"]:  # a cache exists somewhere: GET routes are only candidates if they skip it
        res["uncached_get_routes"] = [r for r in res.get("uncached_get_routes", [])
                                      if not CACHE_LIB_RX.search(C.read_text(os.path.join(root, r["file"]))[0] or "")]
    out = {"candidates": {k: v for k, v in sorted(res.items()) if v}, "infra": infra}
    C.save_json(C.state_path(root, "perf-candidates.json"), out)
    print(json.dumps({"candidates_json": f"{C.STATE_DIR}/perf-candidates.json".replace("\\", "/"),
                      "counts": {k: len(v) for k, v in out["candidates"].items()},
                      "compression": bool(infra["compression"]), "cache_libraries": infra["cache_libraries"],
                      "static_served_by_app": len(infra["static_served_by_app"])}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
