"""Heuristic security hotspots for the make-no-mistakes security gate.

It points the security reviewer at lines worth reading; it does not decide what is a real bug.
Checks (FastAPI / Bun+Hono / Express / Go chi/net-http / SvelteKit / Next.js, any similar stack):
  route_no_auth      route handler with no auth dependency/middleware in reach
  unscoped_query     fetch/update/delete by id with no owner/user/tenant filter nearby
  client_identity    owner/user/tenant id, role, admin flag or price read from request input
  raw_sql            SQL built with string interpolation/concatenation
  secret             hard-coded secret / key / connection string with a password
  frontend_secret    PUBLIC_/NEXT_PUBLIC_/VITE_ variable named like a secret
  cors_wildcard      CORS allowing any origin
  error_leak         stack traces / raw errors / debug mode returned to clients
  weak_hash          md5/sha1/sha256 used for passwords, or Math.random/random for tokens
  xss_sink           dangerouslySetInnerHTML / {@html} / innerHTML with dynamic content
  project-level      no security headers, no rate limiting, no password hashing library found

Usage: python security_scan.py --root . --api backend [--frontend frontend] [--files a b ...]
Writes mnm/security-hotspots.json, prints counts per check.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".svelte", ".vue"}
SKIP_DIRS = C.IGNORED_CHANGE_DIRS | {"migrations", "alembic", "drizzle", "generated", "__generated__"}
TEST = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$|_test\.go$|conftest\.py$")

ROUTE = re.compile(
    r"@(app|router|api|bp|\w+_router)\.(get|post|put|patch|delete|api_route|websocket)\s*\(\s*['\"]([^'\"]*)|"
    r"\b(app|router|api|r|g|e|v1|group|routes|\w+Router|\w+Routes)\.(get|post|put|patch|delete|all|HandleFunc|Handle|Get|Post|Put|Patch|Delete|GET|POST|PUT|PATCH|DELETE)\s*\(\s*[`'\"]((?:(?:GET|POST|PUT|PATCH|DELETE)\s+)?/[^`'\"]*)|"
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b")
AUTH_MARK = re.compile(
    r"(?i)(Depends\(\s*(get_)?(current|require|auth)\w*|CurrentUser|current_user|require_?(auth|user|login|admin|role)|"
    r"authMiddleware|requireAuth|authenticate|isAuthenticated|ensureAuth|withAuth|protected|"
    r"getUser\(|getSession\(|locals\.user|locals\.session|auth\(\)|c\.get\(\s*['\"](user|session)|"
    r"ctx\.Value\(|UserFromContext|userFromCtx|MustUser|middleware\.Auth|RequireUser|session_user|"
    r"verifySession|validateSession|jwt|bearer)")
ROUTER_AUTH = re.compile(
    r"(?i)(APIRouter\([^)]*dependencies\s*=\s*\[[^\]]*Depends|\.use\(\s*['\"]?[^)]*(auth|session|protect|require)|"
    r"r\.Use\(\s*\w*\.?(Auth|Session|Require)|\.Group\([^)]*(auth|Auth)|router\.Use\(\s*\w*(Auth|auth))")
PUBLIC_PATH = re.compile(r"(?i)(health|ready|live|ping|login|logout|signin|signup|sign-in|sign-up|register|"
                         r"auth|oauth|callback|verify|reset|forgot|public|webhook|docs|openapi|robots|sitemap|"
                         r"metrics|status|csrf|^/?$)")
BY_ID = re.compile(
    r"(?i)(\b\w+\.get\(\s*[A-Z]\w*\s*,|\.get_or_404\(|\.filter_by\(\s*id\s*=|\.filter\(\s*\w+\.id\s*==|"
    r"where\(\s*\w+\.id\s*==|\.findUnique\(|\.findFirst\(|\.findById\(|\.findByPk\(|\.findOne\(|"
    r"\.update\(|\.delete\(|\.deleteOne\(|\.updateOne\(|eq\(\s*\w+\.id\s*,|"
    r"where\s+(\w+\.)?id\s*=\s*(\$\d|\?|:\w+|%s)|Get\w*ByID\(|Update\w*\(|Delete\w*\()")
SCOPE = re.compile(r"(?i)(owner_?id|user_?id|tenant_?id|org(anization)?_?id|account_?id|created_?by|author_?id|"
                   r"member|current_user|currentUser|me\.id|user\.id|session\.user|locals\.user|ctx\.user|"
                   r"principal|scope|for_user|ForUser|owned|rls|set_config|app\.user_id)")
OWNER_COMPARE = re.compile(r"(?i)(owner_?id|user_?id|tenant_?id|org_?id|author_?id)\s*(!=|!==|==|===)|"
                           r"(!=|!==|==|===)\s*\w*\.?(owner_?id|user_?id|tenant_?id|org_?id|author_?id)")
CLIENT_ID = re.compile(
    r"(?i)(req\.body|request\.json|request\.form|body|payload|data|params|query|c\.req\.(json|query|param)|"
    r"await\s+request\.json\(\)|r\.FormValue|r\.URL\.Query\(\))\s*(\.|\[\s*['\"]|\.get\(\s*['\"])\s*"
    r"(owner_?id|user_?id|tenant_?id|org_?id|role|is_?admin|isAdmin|price|amount|total|discount)\b")
RAW_SQL = re.compile(
    r"(?i)(\bf\"[^\"]*\b(select|insert|update|delete)\b[^\"]*\{|\bf'[^']*\b(select|insert|update|delete)\b[^']*\{|"
    r"\b(select|insert\s+into|update|delete\s+from)\b[^;\n]*['\"`]\s*\+\s*\w|"
    r"`[^`]*\b(select|insert|update|delete)\b[^`]*\$\{|"
    r"\.(raw|execute|query|exec|queryRawUnsafe|executeRawUnsafe)\(\s*f?['\"`][^'\"`]*(%s|\{|\$\{)[^'\"`]*['\"`]\s*(%|\.format|\+)|"
    r"fmt\.Sprintf\(\s*\"[^\"]*\b(SELECT|INSERT|UPDATE|DELETE|WHERE)\b)")
SECRET = [
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^:\s/'\"]+:[^@\s'\"$]{3,}@(?!localhost|127\.0\.0\.1|db\b|postgres\b)"),
    re.compile(r"(?i)\b(secret|password|passwd|api_?key|private_?key|client_?secret|jwt_?secret)\w*\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
]
SECRET_OK = re.compile(r"(?i)(example|changeme|placeholder|your[_-]|xxx|test|dummy|fake|<|\{\{|process\.env|os\.environ|getenv)")
FRONTEND_SECRET = re.compile(r"\b(NEXT_PUBLIC_|PUBLIC_|VITE_|EXPO_PUBLIC_)\w*(SECRET|PRIVATE|PASSWORD|SERVICE_ROLE|TOKEN|API_KEY)\w*")
CORS_WILD = re.compile(r"(?i)(allow_origins\s*=\s*\[\s*['\"]\*|origin\s*:\s*['\"]\*['\"]|origin\s*:\s*true|"
                       r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|AllowedOrigins:\s*\[\]string\{\s*\"\*\"|"
                       r"AllowAllOrigins\s*:\s*true|\bcors\(\s*\))")
ERROR_LEAK = re.compile(r"(?i)(traceback\.format_exc|err\.stack|error\.stack|\.Error\(\)\s*\)|debug\s*=\s*True|"
                        r"str\(e\)|str\(exc\)|detail\s*=\s*str\(|message:\s*err(or)?\.message|"
                        r"http\.Error\(\s*w\s*,\s*err\.Error\(\))")
WEAK_HASH = re.compile(r"(?i)((md5|sha1|sha256)\w*\([^)]*pass|hashlib\.(md5|sha1)\(|createHash\(\s*['\"](md5|sha1)['\"]|"
                       r"Math\.random\(\)[^;\n]*(token|secret|code|id)|random\.(random|randint|choice)\([^)]*\)[^\n]*(token|secret|code))")
XSS = re.compile(r"(dangerouslySetInnerHTML|\{@html\s|\.innerHTML\s*=|v-html=)")
HEADERS_LIB = re.compile(r"(?i)(helmet|secure-headers|secureHeaders|secure_headers|Strict-Transport-Security|"
                         r"Content-Security-Policy|X-Content-Type-Options|SecurityHeaders|unrolled/secure)")
RATE_LIB = re.compile(r"(?i)(rate.?limit|slowapi|limiter|throttl|httprate|tollbooth)")
HASH_LIB = re.compile(r"(?i)(argon2|bcrypt|scrypt|pwdlib|passlib|Bun\.password)")


def list_files(root, bases, only):
    if only:
        return [f.replace("\\", "/") for f in only if os.path.splitext(f)[1] in CODE_EXT]
    out = []
    for base in bases:
        for d, dirs, files in os.walk(os.path.join(root, base)):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for f in files:
                if os.path.splitext(f)[1] in CODE_EXT:
                    out.append(os.path.relpath(os.path.join(d, f), root).replace("\\", "/"))
    return sorted(out)


def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def window(lines, i, before, after):
    return "\n".join(lines[max(0, i - before): i + after + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--api", required=True, help="backend directory")
    ap.add_argument("--frontend", help="frontend directory (for secrets/XSS checks)")
    ap.add_argument("--files", nargs="*", help="limit to these files (existing-project mode)")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    bases = [a.api] + ([a.frontend] if a.frontend else [])
    files = list_files(root, bases, a.files)
    hits, seen = [], set()
    project = {"headers": False, "rate_limit": False, "password_hash": False}

    def add(check, path, i, line, note=""):
        key = (check, path, i)
        if key in seen:
            return
        seen.add(key)
        hits.append({"check": check, "file": path, "line": i + 1, "code": line.strip()[:160], "note": note})

    for path in files:
        lines = read_lines(os.path.join(root, path))
        if not lines:
            continue
        text = "\n".join(lines)
        is_test = bool(TEST.search(path))
        is_frontend = bool(a.frontend) and path.startswith(a.frontend.rstrip("/") + "/")
        if HEADERS_LIB.search(text):
            project["headers"] = True
        if RATE_LIB.search(text):
            project["rate_limit"] = True
        if HASH_LIB.search(text):
            project["password_hash"] = True
        if is_test:
            continue
        file_router_auth = bool(ROUTER_AUTH.search(text))
        for i, line in enumerate(lines):
            m = ROUTE.search(line)
            if m and not is_frontend:
                path_str = next((g for g in (m.group(3), m.group(6)) if g is not None), "") or ""
                # The handler ends where the next route starts, so a neighbour's auth doesn't count.
                stop = min(len(lines), i + 40)
                end = next((j for j in range(i + 1, stop) if ROUTE.search(lines[j])), stop)
                handler = "\n".join(lines[max(0, i - 2):end])
                if not file_router_auth and not AUTH_MARK.search(handler) and not PUBLIC_PATH.search(path_str):
                    add("route_no_auth", path, i, line, f"route '{path_str or m.group(0)}' has no auth marker nearby")
            if BY_ID.search(line) and not m and not is_frontend:
                # The filter must be in the query itself: this line, plus continuation lines only
                # while the call's parentheses are still open (max 3).
                q_end, depth = i + 1, line.count("(") - line.count(")")
                while depth > 0 and q_end < min(len(lines), i + 4):
                    depth += lines[q_end].count("(") - lines[q_end].count(")")
                    q_end += 1
                if not SCOPE.search("\n".join(lines[i:q_end])):
                    after = "\n".join(lines[i + 1:min(len(lines), i + 7)])
                    if OWNER_COMPARE.search(after):
                        add("unscoped_query", path, i, line, "load-then-compare: ownership checked after "
                            "fetching; prefer scoping inside the query and returning 404")
                    else:
                        add("unscoped_query", path, i, line, "by-id access without an owner/tenant filter in the query")
            if CLIENT_ID.search(line):
                add("client_identity", path, i, line, "server-owned field read from request input")
            if RAW_SQL.search(line):
                add("raw_sql", path, i, line, "SQL built by interpolation/concatenation")
            if any(not SECRET_OK.search(sm.group(0)) for rx in SECRET for sm in rx.finditer(line)):
                add("secret", path, i, line, "hard-coded secret")
            if FRONTEND_SECRET.search(line):
                add("frontend_secret", path, i, line, "secret-like name exposed to the browser bundle")
            if CORS_WILD.search(line):
                add("cors_wildcard", path, i, line, "CORS allows any origin")
            if ERROR_LEAK.search(line):
                add("error_leak", path, i, line, "raw error/stack/debug may reach the client")
            if WEAK_HASH.search(line):
                add("weak_hash", path, i, line, "weak hash or non-crypto randomness for a secret")
            if XSS.search(line):
                add("xss_sink", path, i, line, "HTML sink: make sure the content is sanitized")

    if not a.files:  # project-level checks only make sense on a full scan
        if not project["headers"]:
            hits.append({"check": "missing_security_headers", "file": a.api, "line": 0, "code": "",
                         "note": "no security-headers middleware or header names found"})
        if not project["rate_limit"]:
            hits.append({"check": "missing_rate_limit", "file": a.api, "line": 0, "code": "",
                         "note": "no rate limiter found (auth and write endpoints need one)"})
        if not project["password_hash"]:
            hits.append({"check": "missing_password_hash", "file": a.api, "line": 0, "code": "",
                         "note": "no argon2/bcrypt/scrypt usage found (fine only if there are no passwords)"})

    counts = {}
    for h in hits:
        counts[h["check"]] = counts.get(h["check"], 0) + 1
    out = {"root": root, "scanned_files": len(files), "counts": counts, "hotspots": hits}
    C.save_json(C.mnm_path(root, "security-hotspots.json"), out)
    print(f"security_scan: {len(files)} files · {len(hits)} hotspots → mnm/security-hotspots.json")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
