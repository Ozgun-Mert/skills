"""Build docs/.backend-checks/index.json: the compact map every check starts from.

One pass over the API path (and, lightly, the extra paths) with no LLM involved:
files + sha256 + line counts + rough import graph, detected stack and runtime version,
every dependency with its resolved version, per-category hotspots (file -> line numbers),
a secrets scan (tracked files, git history, source, frontend-exposed env vars) and the
test command.

Usage: python index.py --root . --api api/ [--extra web/ shared/]
Prints a short summary; the full map goes to docs/.backend-checks/index.json.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

# --------------------------------------------------------------------------- hotspots
# Heuristic, language-agnostic patterns. They only point agents at lines worth reading;
# agents decide what is a real problem.
H = {
    "routes": r"\b(app|router|server|api|route|r|e|g|mux|fastify)\.(get|post|put|patch|delete|all|route|use|HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\s*\(|"
              r"@(Get|Post|Put|Patch|Delete|All)\s*\(|@(app|router|api|bp|blueprint)\.(get|post|put|patch|delete|route|api_route|websocket)\s*\(|"
              r"\b(re_)?path\s*\(\s*r?['\"]|@(Get|Post|Put|Patch|Delete|Request)Mapping|Route::(get|post|put|patch|delete|resource|apiResource)|"
              r"^\s*(get|post|put|patch|delete|resources?)\s+['\":]|\[Http(Get|Post|Put|Patch|Delete)|\.Map(Get|Post|Put|Patch|Delete)\s*\(",
    "db": r"\.(findMany|findUnique|findFirst|findById|findOne|findAll|findByPk|insertOne|insertMany|updateOne|updateMany|deleteOne|deleteMany|"
          r"upsert|aggregate|createQueryBuilder|getRepository|query|execute|executemany|raw|\$queryRaw\w*|\$executeRaw\w*|\$transaction|"
          r"transaction|destroy|bulkCreate|Query|QueryRow|Exec|QueryContext|ExecContext)\s*\(|\bobjects\.\w+\(|\bsession\.(query|execute|add|delete|merge)\(|"
          r"\bDB::|\bprisma\.\w+\.\w+\(|\bknex\b|\bdb\.\w+\.\w+\(|(?i:\b(select\s+[\w*,.\s]+\s+from|insert\s+into|update\s+\w+\s+set|delete\s+from)\b)",
    "raw_sql": r"(?i)(\b(select|insert|update|delete|where|order\s+by|values)\b.*(\$\{|\"\s*\+|'\s*\+|\+\s*\w+|%s['\"]\s*%|\.format\(|f['\"]))|"
               r"(f['\"].*\b(select|insert|update|delete|where)\b)|queryRawUnsafe|executeRawUnsafe|\.raw\(\s*[`'\"].*\$\{|text\(\s*f['\"]|\$where",
    "mass_assignment": r"\.\.\.\s*req\.body|\.\.\.\s*body\b|\b(create|update|insert|save|fill|assign|build|upsert)\w*\(\s*(req\.body|request\.body|body|data|payload|request\.data|request\.json\(\))\s*[,)]|"
                       r"Object\.assign\([^)]*req\.body|\*\*\s*(request\.json|request\.data|data|payload|body|\w+\.dict\(\)|\w+\.model_dump\(\))|"
                       r"\$request->all\(\)|data:\s*req\.body|setattr\(\s*\w+\s*,\s*(k|key|field)|Object\.(keys|values|entries)\(\s*req\.body|\b\w+\(\s*\*\*\s*\w+\s*\)",
    "trusts_client": r"(req\.body|request\.body|body|request\.json|request\.data|payload|dto|item|items\[\w*\]|i)\.?\[?['\"]?(price|total|amount|subtotal|discount|unit_?price|cost|fee|tax|isAdmin|is_admin|role|userId|user_id|ownerId|owner_id|restaurantId|restaurant_id|tenantId|tenant_id)\b",
    "uploads": r"(?i)multer|busboy|formidable|UploadFile|FileField|ImageField|MultipartFile|IFormFile|FormFile|upload|putObject|PutObjectCommand|getSignedUrl|presign|->file\(|\.files?\b\s*[\[.]",
    "cors": r"(?i)\bcors\b|Access-Control-Allow|allow_origins|AllowOrigins|@CrossOrigin|CORS_|corsOptions|origin\s*:",
    "headers": r"(?i)helmet|setHeader|res\.header|res\.set\(|Strict-Transport|Content-Security-Policy|X-Frame|X-Content-Type|Referrer-Policy|SecurityMiddleware|SECURE_[A-Z_]+|x-powered-by|add_header|hsts|secure_headers|talisman",
    "rate_limit": r"(?i)rate.?limit|throttl|slow.?down|limiter|express-brute|slowapi|ratelimit|bottleneck",
    "websocket": r"(?i)socket\.io|\bio\.on\(|\bws\b|WebSocket|websocket|@WebSocketGateway|SubscribeMessage|channels\.|\.on\(\s*['\"]connection|upgrade",
    "auth": r"(?i)\bjwt\b|jsonwebtoken|jose|passport|bcrypt|argon2|scrypt|pbkdf2|session|cookie|authenticat|authoriz|isAdmin|is_admin|\brole|req\.user|current_user|"
            r"Depends\(|login_required|PreAuthorize|middleware|verifyToken|requireAuth|guard|permission|reset.?token|refresh.?token|logout|sign\(|verify\(",
    "crypto": r"(?i)\bmd5\b|\bsha1\b|createHash|Math\.random|random\.random|random\.randint|rand\(\)|createCipher|\bcipher|\biv\b|hashlib|uuid\.uuid1|SecureRandom|crypto\.random|secrets\.token|nanoid",
    "payments": r"(?i)stripe|iyzico|iyzipay|paypal|braintree|adyen|paddle|checkout|payment|webhook|\bcharge|refund|invoice|\bpay\b|\bpay\(",
    "logging": r"console\.(log|info|warn|error|debug)|\blogger\.|\blogging\.|\blog\.(Print|Info|Error|Debug|Warn|info|error|debug|warn)|winston|pino|bunyan|print\(",
    "error_handler": r"\(\s*err\s*,\s*req\s*,\s*res\s*,\s*next\s*\)|@ExceptionHandler|exception_handler|errorHandler|ErrorHandler|HTTPException|\.stack\b|traceback|"
                     r"catch\s*\(|except\s+\w*|rescue_from|res\.status\(\s*5\d\d|DEBUG\s*=|debug\s*:\s*true|NODE_ENV",
    "validation": r"(?i)\bzod\b|z\.object|\bjoi\b|\byup\b|celebrate|class-validator|express-validator|pydantic|BaseModel|marshmallow|Validator|@Valid|validate\(|schema\.parse|safeParse|limit\s*=|\.limit\(|take\s*:|body-parser|json\(\s*\{\s*limit",
    "injection": r"(?i)child_process|\bexec\(|execSync|spawn\(|subprocess|os\.system|popen|shell\s*=\s*True|eval\(|new Function\(|vm\.run|\bpath\.join\(|path\.resolve\(|sendFile|"
                 r"res\.download|open\(|readFile|createReadStream|axios\.(get|post)\(\s*(req|url|body)|fetch\(\s*(req|url|body|`)|requests\.(get|post)\(|urlopen|"
                 r"__proto__|merge\(|deepmerge|lodash|_\.merge|new RegExp\(|re\.compile\(|pickle\.loads|yaml\.load\(|unserialize|render_template_string|Template\(",
    "cache": r"(?i)\bcache\b|redis|memcache|lru|\.setex\(|\.expire\(|ttl|@cache|cache_page|lru_cache|node-cache",
    "type_switch": r"\bswitch\s*\(|\bmatch\s+\w+.*:\s*$|\bcase\s+['\"]|if\s*\(?\s*[\w.\[\]'\"]*\b(type|method|provider|kind|channel|role|gateway|strategy|mode|status|category|platform)\w*\s*(===?|==|!==?)|"
                   r"elif\s+[\w.\[\]'\"]*\b(type|method|provider|kind|channel|role|gateway|strategy|mode|status|category|platform)\w*\s*==",
    "types": r"\b(interface|type)\s+\w+\s*[={<]|\bclass\s+\w+\(BaseModel\)|@dataclass|\bTypedDict\b|export\s+(interface|type|enum)\b",
}
EXTRA_H = {
    "client_values": r"\b(price|total|amount|subtotal|discount|unitPrice|unit_price|isAdmin|is_admin|role|userId|user_id|restaurantId|tenantId)\b\s*[:=]",
    "frontend_env": r"\b(NEXT_PUBLIC_|VITE_|REACT_APP_|NUXT_PUBLIC_|PUBLIC_|EXPO_PUBLIC_|GATSBY_)\w*(SECRET|PRIVATE|PASSWORD|TOKEN|KEY)\w*",
    "types": H["types"],
}
HOT = {k: re.compile(v) for k, v in H.items()}
EXTRA_HOT = {k: re.compile(v) for k, v in EXTRA_H.items()}
MAX_HITS_PER_FILE = 60

# --------------------------------------------------------------------------- files

def list_files(root, base, is_repo):
    base_abs = os.path.join(root, base)
    out = []
    if is_repo:
        code, txt = C.git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", base)
        if code == 0:
            for p in txt.splitlines():
                p = p.strip().strip('"')
                if p and os.path.isfile(os.path.join(root, p)):
                    out.append(p.replace("\\", "/"))
            return [p for p in out if not set(p.split("/")) & C.EXCLUDE_DIRS]
    for d, dirs, files in os.walk(base_abs):
        dirs[:] = [x for x in dirs if x not in C.EXCLUDE_DIRS and not x.startswith(".")]
        for f in files:
            out.append(C.rel(os.path.join(d, f), root))
    return out


def wanted(p):
    name = p.rsplit("/", 1)[-1]
    if name.endswith((".min.js", ".map", ".d.ts.map", ".lock")) or name in C.MANIFEST_NAMES:
        return None
    ext = os.path.splitext(name)[1].lower()
    if ext in C.CODE_EXTS:
        return C.CODE_EXTS[ext]
    if C.CONFIG_NAMES.search(p):
        return "config"
    return None


JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|require\s*\(\s*|export\s[^'"]*?from\s*)['"](\.{1,2}/[^'"]+)['"]""")
PY_REL = re.compile(r"^\s*from\s+(\.+)([\w.]*)\s+import\s+([\w*, ()]+)", re.M)
PY_ABS = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+\(?([\w, ]+)|import\s+([\w.]+))", re.M)
JS_EXT = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"]


def resolve_js(src, spec, known):
    base = os.path.normpath(os.path.join(os.path.dirname(src), spec)).replace("\\", "/")
    cands = [base]
    stem = re.sub(r"\.(js|mjs|cjs|jsx)$", "", base)
    cands += [stem + e for e in JS_EXT] + [base + "/index" + e for e in JS_EXT]
    for c in cands:
        if c in known:
            return c
    return None


def resolve_py(src, text, known, py_roots):
    found = set()
    for m in PY_REL.finditer(text):
        dots, mod, names = m.group(1), m.group(2), m.group(3)
        d = os.path.dirname(src)
        for _ in range(len(dots) - 1):
            d = os.path.dirname(d)
        parts = [p for p in mod.split(".") if p]
        bases = [os.path.join(d, *parts)] if parts else []
        if not parts:
            bases += [os.path.join(d, n.strip(" ()")) for n in names.split(",") if n.strip(" ()*")]
        for b in bases:
            b = b.replace("\\", "/")
            for c in (b + ".py", b + "/__init__.py"):
                if c in known:
                    found.add(c)
    for m in PY_ABS.finditer(text):
        mod = m.group(1) or m.group(3)
        parts = mod.split(".")
        names = [n.strip() for n in (m.group(2) or "").split(",") if n.strip()]
        for r in py_roots:
            pre = ([r] if r else [])
            for n in names:  # `from pkg import module` imports a submodule
                b = "/".join(pre + parts + [n])
                if b + ".py" in known:
                    found.add(b + ".py")
            for k in range(len(parts), 0, -1):
                b = "/".join(pre + parts[:k])
                hit = next((c for c in (b + ".py", b + "/__init__.py") if c in known), None)
                if hit:
                    found.add(hit)
                    break
    found.discard(src)
    return sorted(found)

# --------------------------------------------------------------------------- dependencies

def _clean_ver(v):
    v = (v or "").strip().strip("'\"")
    m = re.search(r"\d+(\.\d+)*([\-+.][0-9A-Za-z.\-]+)?", v)
    return m.group(0) if m else None


def parse_npm(dirpath, relpath):
    deps = {}
    pj = C.load_json(os.path.join(dirpath, "package.json"), {}) or {}
    direct = {}
    for sec, dev in (("dependencies", False), ("devDependencies", True), ("optionalDependencies", False)):
        for n, v in (pj.get(sec) or {}).items():
            direct[n] = (v, dev)
    lock = C.load_json(os.path.join(dirpath, "package-lock.json")) or C.load_json(os.path.join(dirpath, "npm-shrinkwrap.json"))
    if lock and lock.get("packages"):
        for k, meta in lock["packages"].items():
            if not k or "node_modules/" not in k or not meta.get("version"):
                continue
            name = k.rsplit("node_modules/", 1)[1]
            deps[(name, meta["version"])] = {"dev": bool(meta.get("dev")), "direct": k.count("node_modules/") == 1 and name in direct}
    elif lock and lock.get("dependencies"):
        def walk(d, depth):
            for n, meta in d.items():
                if meta.get("version"):
                    deps[(n, meta["version"])] = {"dev": bool(meta.get("dev")), "direct": depth == 0 and n in direct}
                walk(meta.get("dependencies") or {}, depth + 1)
        walk(lock["dependencies"], 0)
    yl = os.path.join(dirpath, "yarn.lock")
    if not deps and os.path.exists(yl):
        txt = open(yl, encoding="utf-8", errors="replace").read()
        for block in re.split(r"\n(?=\S)", txt):
            head = block.split("\n", 1)[0]
            m = re.match(r"""^"?(@?[^@"\s,]+)@""", head)
            v = re.search(r"""\n\s+version:?\s+"?([^"\s]+)""", block)
            if m and v:
                n = m.group(1)
                deps[(n, v.group(1))] = {"dev": direct.get(n, (0, False))[1], "direct": n in direct}
    pl = os.path.join(dirpath, "pnpm-lock.yaml")
    if not deps and os.path.exists(pl):
        txt = open(pl, encoding="utf-8", errors="replace").read()
        sec = re.split(r"\n(?:packages|snapshots):\s*\n", txt)
        body = sec[1] if len(sec) > 1 else txt
        for m in re.finditer(r"""^\s{2}['"]?/?(@?[^@\s'"/]+(?:/[^@\s'"]+)?)@(\d[^:'"()\s]*)""", body, re.M):
            n = m.group(1)
            deps[(n, m.group(2))] = {"dev": direct.get(n, (0, False))[1], "direct": n in direct}
    if not deps:  # no lockfile: approximate from declared ranges
        for n, (v, dev) in direct.items():
            cv = _clean_ver(v)
            if cv:
                deps[(n, cv)] = {"dev": dev, "direct": True, "approx": True}
    return [{"ecosystem": "npm", "name": n, "version": v, "manifest": relpath, **meta} for (n, v), meta in deps.items()]


def parse_python(dirpath, relpath):
    deps = {}
    for lock in ("poetry.lock", "uv.lock"):
        p = os.path.join(dirpath, lock)
        if os.path.exists(p):
            txt = open(p, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r'\[\[package\]\]\s*\nname\s*=\s*"([^"]+)"\s*\nversion\s*=\s*"([^"]+)"', txt):
                deps[(m.group(1), m.group(2))] = {"direct": False}
    p = os.path.join(dirpath, "Pipfile.lock")
    if os.path.exists(p):
        j = C.load_json(p, {}) or {}
        for sec in ("default", "develop"):
            for n, meta in (j.get(sec) or {}).items():
                v = _clean_ver(meta.get("version"))
                if v:
                    deps[(n, v)] = {"direct": False, "dev": sec == "develop"}
    direct = set()
    for f in sorted(os.listdir(dirpath)):
        if re.match(r"requirements.*\.(txt|in)$", f):
            for line in open(os.path.join(dirpath, f), encoding="utf-8", errors="replace"):
                line = line.split("#")[0].strip()
                m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|===|~=|>=)\s*([0-9][^\s;,]*)", line)
                if m:
                    n = m.group(1)
                    direct.add(n.lower())
                    if m.group(3) in ("==", "===") or not any(k[0].lower() == n.lower() for k in deps):
                        deps[(n, m.group(4))] = {"direct": True, "dev": "dev" in f, "approx": m.group(3) not in ("==", "===")}
    pp = os.path.join(dirpath, "pyproject.toml")
    if os.path.exists(pp):
        txt = open(pp, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"""['"]([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|>=|~=|\^)\s*([0-9][^'",;\s]*)""", txt):
            direct.add(m.group(1).lower())
            if not any(k[0].lower() == m.group(1).lower() for k in deps):
                deps[(m.group(1), m.group(4))] = {"direct": True, "approx": m.group(3) != "=="}
        for m in re.finditer(r'^([A-Za-z0-9_.\-]+)\s*=\s*"[\^~>=]*([0-9][^"]*)"', txt, re.M):
            if m.group(1).lower() != "python" and not any(k[0].lower() == m.group(1).lower() for k in deps):
                direct.add(m.group(1).lower())
                deps[(m.group(1), m.group(2))] = {"direct": True, "approx": True}
    out = []
    for (n, v), meta in deps.items():
        meta["direct"] = meta.get("direct") or n.lower() in direct
        out.append({"ecosystem": "PyPI", "name": n, "version": v, "manifest": relpath, **meta})
    return out


def parse_other(dirpath, relpath, name):
    out = []
    p = os.path.join(dirpath, name)
    txt = open(p, encoding="utf-8", errors="replace").read()
    if name == "go.mod":
        for m in re.finditer(r"^\s*(?:require\s+)?([\w.\-]+\.[\w.\-/]+)\s+(v[0-9][^\s]*)(\s*//\s*indirect)?", txt, re.M):
            out.append({"ecosystem": "Go", "name": m.group(1), "version": m.group(2), "direct": not m.group(3)})
    elif name == "pom.xml":
        props = dict(re.findall(r"<([\w.\-]+)>([^<]+)</\1>", (re.search(r"<properties>(.*?)</properties>", txt, re.S) or [None, ""])[1] if re.search(r"<properties>(.*?)</properties>", txt, re.S) else ""))
        for d in re.findall(r"<dependency>(.*?)</dependency>", txt, re.S):
            g = re.search(r"<groupId>([^<]+)", d)
            a = re.search(r"<artifactId>([^<]+)", d)
            v = re.search(r"<version>([^<]+)", d)
            if g and a and v:
                ver = v.group(1)
                pm = re.match(r"\$\{([^}]+)\}", ver)
                if pm:
                    ver = props.get(pm.group(1), ver)
                out.append({"ecosystem": "Maven", "name": f"{g.group(1)}:{a.group(1)}", "version": ver, "direct": True})
    elif name.startswith("build.gradle"):
        for m in re.finditer(r"""(implementation|api|compile|runtimeOnly|compileOnly|testImplementation)\s*\(?\s*['"]([^:'"]+):([^:'"]+):([^'"@]+)['"]""", txt):
            out.append({"ecosystem": "Maven", "name": f"{m.group(2)}:{m.group(3)}", "version": m.group(4), "direct": True,
                        "dev": m.group(1).startswith("test")})
    elif name == "composer.lock":
        j = json.loads(txt or "{}")
        for sec in ("packages", "packages-dev"):
            for pkg in j.get(sec) or []:
                out.append({"ecosystem": "Packagist", "name": pkg.get("name"), "version": str(pkg.get("version", "")).lstrip("v"),
                            "direct": False, "dev": sec.endswith("dev")})
    elif name == "Gemfile.lock":
        for m in re.finditer(r"^ {4}([A-Za-z0-9_.\-]+) \(([0-9][^)]*)\)", txt, re.M):
            out.append({"ecosystem": "RubyGems", "name": m.group(1), "version": m.group(2).split("-")[0], "direct": False})
    elif name == "Cargo.lock":
        for m in re.finditer(r'\[\[package\]\]\s*\nname\s*=\s*"([^"]+)"\s*\nversion\s*=\s*"([^"]+)"', txt):
            out.append({"ecosystem": "crates.io", "name": m.group(1), "version": m.group(2), "direct": False})
    elif name.endswith(".csproj"):
        for m in re.finditer(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"', txt):
            out.append({"ecosystem": "NuGet", "name": m.group(1), "version": m.group(2), "direct": True})
    for d in out:
        d["manifest"] = relpath
    return out


def find_manifest_dirs(root, api, all_files):
    """Dirs holding manifests: inside the API path, plus the API path's ancestors up to root."""
    dirs = set()
    for p in all_files:
        if p.rsplit("/", 1)[-1] in C.MANIFEST_NAMES or p.endswith(".csproj"):
            dirs.add(os.path.dirname(p))
    d = os.path.normpath(api).replace("\\", "/")
    while True:
        dirs.add("" if d in (".", "") else d)
        if d in (".", ""):
            break
        d = os.path.dirname(d) or "."
    return sorted(x for x in dirs if os.path.isdir(os.path.join(root, x or ".")))


def collect_dependencies(root, api, manifest_files):
    deps, manifests = [], []
    for d in find_manifest_dirs(root, api, manifest_files):
        full = os.path.join(root, d or ".")
        names = set(os.listdir(full))
        for n in sorted(names):
            if n in C.MANIFEST_NAMES or n.endswith(".csproj"):
                rp = (d + "/" + n) if d else n
                txt, b = C.read_text(os.path.join(full, n), limit=50_000_000)
                manifests.append({"path": rp, "sha256": C.sha256_bytes(b or b"")})
        rpath = d or "."
        try:
            if "package.json" in names:
                deps += parse_npm(full, rpath)
            if names & {"requirements.txt", "requirements-dev.txt", "requirements.in", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile.lock"} \
                    or any(re.match(r"requirements.*\.txt$", n) for n in names):
                deps += parse_python(full, rpath)
            for n in sorted(names):
                if n in ("go.mod", "pom.xml", "build.gradle", "build.gradle.kts", "composer.lock", "Gemfile.lock", "Cargo.lock") or n.endswith(".csproj"):
                    deps += parse_other(full, rpath, n)
        except (OSError, ValueError) as e:
            deps.append({"error": f"{rpath}: {e}"})
    seen, uniq = set(), []
    for x in deps:
        k = (x.get("ecosystem"), x.get("name"), x.get("version"))
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq, manifests

# --------------------------------------------------------------------------- stack / runtime / tests

FRAMEWORKS = {
    "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS", "koa": "Koa", "@hapi/hapi": "hapi", "hono": "Hono",
    "next": "Next.js", "@trpc/server": "tRPC", "apollo-server": "Apollo", "@apollo/server": "Apollo", "socket.io": "Socket.IO", "ws": "ws",
    "django": "Django", "djangorestframework": "Django REST", "fastapi": "FastAPI", "flask": "Flask", "starlette": "Starlette",
    "github.com/gin-gonic/gin": "Gin", "github.com/labstack/echo/v4": "Echo", "github.com/gofiber/fiber/v2": "Fiber", "github.com/go-chi/chi/v5": "chi",
    "org.springframework.boot:spring-boot-starter-web": "Spring Boot", "laravel/framework": "Laravel", "rails": "Rails", "sinatra": "Sinatra",
    "Microsoft.AspNetCore.App": "ASP.NET Core", "actix-web": "Actix", "axum": "Axum",
}
DATA = {
    "prisma": "Prisma", "@prisma/client": "Prisma", "typeorm": "TypeORM", "sequelize": "Sequelize", "drizzle-orm": "Drizzle", "mongoose": "Mongoose",
    "mongodb": "MongoDB driver", "knex": "Knex", "pg": "node-postgres", "mysql2": "mysql2", "mysql": "mysql", "better-sqlite3": "SQLite", "sqlite3": "SQLite",
    "ioredis": "Redis", "redis": "Redis", "sqlalchemy": "SQLAlchemy", "SQLAlchemy": "SQLAlchemy", "psycopg2": "psycopg2", "psycopg2-binary": "psycopg2",
    "psycopg": "psycopg", "asyncpg": "asyncpg", "pymongo": "PyMongo", "motor": "Motor", "tortoise-orm": "Tortoise", "peewee": "peewee",
    "gorm.io/gorm": "GORM", "github.com/jmoiron/sqlx": "sqlx", "github.com/jackc/pgx/v5": "pgx", "org.hibernate:hibernate-core": "Hibernate",
    "diesel": "Diesel", "sqlx": "sqlx",
}
SECURITY_LIBS = ["helmet", "@fastify/helmet", "cors", "@fastify/cors", "express-rate-limit", "rate-limiter-flexible", "@nestjs/throttler",
                 "@fastify/rate-limit", "slowapi", "django-ratelimit", "django-cors-headers", "flask-cors", "flask-limiter", "flask-talisman",
                 "secure", "csurf", "csrf-csrf", "multer", "busboy", "formidable", "file-type", "zod", "joi", "yup", "class-validator",
                 "express-validator", "pydantic", "bcrypt", "bcryptjs", "argon2", "jsonwebtoken", "jose", "passport", "python-jose", "PyJWT",
                 "passlib", "itsdangerous", "express-session", "cookie-parser", "hpp", "express-mongo-sanitize"]


def detect_stack(deps, langs):
    names = {d["name"]: d for d in deps if d.get("name")}
    lower = {k.lower(): v for k, v in names.items()}

    def pick(table):
        out = []
        for k, label in table.items():
            d = names.get(k) or lower.get(k.lower())
            if d and label not in [x["name"] for x in out]:
                out.append({"name": label, "package": d["name"], "version": d["version"]})
        return out
    sec = []
    for k in SECURITY_LIBS:
        d = names.get(k) or lower.get(k.lower())
        if d:
            sec.append(f"{d['name']}@{d['version']}")
    return {"languages": langs, "frameworks": pick(FRAMEWORKS), "data": pick(DATA), "security_libs": sec}


def detect_runtime(root, api, files):
    found = []

    def rd(p):
        t, _ = C.read_text(os.path.join(root, p))
        return t or ""
    cand_dirs = find_manifest_dirs(root, api, [])
    for d in cand_dirs:
        pre = (d + "/") if d else ""
        for fn, prod in ((".nvmrc", "nodejs"), (".node-version", "nodejs"), (".python-version", "python"), (".ruby-version", "ruby"), ("runtime.txt", "python")):
            if os.path.exists(os.path.join(root, pre + fn)):
                v = _clean_ver(rd(pre + fn))
                if v:
                    found.append({"product": prod, "version": v, "source": pre + fn})
        pj = C.load_json(os.path.join(root, pre + "package.json"), {}) or {}
        if (pj.get("engines") or {}).get("node"):
            found.append({"product": "nodejs", "version": _clean_ver(pj["engines"]["node"]), "source": pre + "package.json engines", "approx": True})
        if os.path.exists(os.path.join(root, pre + "go.mod")):
            m = re.search(r"^go\s+(\d+\.\d+(\.\d+)?)", rd(pre + "go.mod"), re.M)
            if m:
                found.append({"product": "go", "version": m.group(1), "source": pre + "go.mod"})
        if os.path.exists(os.path.join(root, pre + "pyproject.toml")):
            m = re.search(r"requires-python\s*=\s*['\"][^0-9]*([0-9.]+)", rd(pre + "pyproject.toml"))
            if m:
                found.append({"product": "python", "version": m.group(1), "source": pre + "pyproject.toml", "approx": True})
        cj = C.load_json(os.path.join(root, pre + "composer.json"), {}) or {}
        if (cj.get("require") or {}).get("php"):
            found.append({"product": "php", "version": _clean_ver(cj["require"]["php"]), "source": pre + "composer.json", "approx": True})
    for p in files:
        name = p.rsplit("/", 1)[-1].lower()
        if name.startswith("dockerfile"):
            for m in re.finditer(r"^\s*FROM\s+(?:--platform=\S+\s+)?([\w./\-]+):([0-9][\w.\-]*)", rd(p), re.M | re.I):
                img, tag = m.group(1).rsplit("/", 1)[-1], m.group(2)
                prod = {"node": "nodejs", "python": "python", "golang": "go", "php": "php", "ruby": "ruby",
                        "eclipse-temurin": "eclipse-temurin", "openjdk": "eclipse-temurin", "amazoncorretto": "amazon-corretto"}.get(img)
                if prod:
                    found.append({"product": prod, "version": _clean_ver(tag), "source": p})
        elif name.endswith(".csproj"):
            m = re.search(r"<TargetFramework>net(\d+\.\d+)", rd(p))
            if m:
                found.append({"product": "dotnet", "version": m.group(1), "source": p})
    seen, out = set(), []
    for f in found:
        k = (f["product"], f["version"])
        if f["version"] and k not in seen:
            seen.add(k)
            out.append(f)
    return out


def detect_tests(root, api, files):
    test_files = [p for p in files if C.is_test_path(p) and os.path.splitext(p)[1] in C.CODE_EXTS]
    res = {"command": None, "cwd": None, "test_files": len(test_files), "deps_installed": None, "note": None}
    for d in find_manifest_dirs(root, api, []):
        pre = (d + "/") if d else ""
        full = os.path.join(root, d or ".")
        pj = C.load_json(os.path.join(full, "package.json"))
        if pj is not None:
            t = (pj.get("scripts") or {}).get("test", "")
            if t and "no test specified" not in t:
                pm = "pnpm" if os.path.exists(os.path.join(full, "pnpm-lock.yaml")) else "yarn" if os.path.exists(os.path.join(full, "yarn.lock")) else "npm"
                res.update(command=f"{pm} test", cwd=d or ".", deps_installed=os.path.isdir(os.path.join(full, "node_modules")) or not (pj.get("dependencies") or pj.get("devDependencies")))
                return res
        if any(os.path.exists(os.path.join(full, f)) for f in ("pytest.ini", "conftest.py", "tox.ini")) or \
                (os.path.exists(os.path.join(full, "pyproject.toml")) and "[tool.pytest" in (C.read_text(os.path.join(full, "pyproject.toml"))[0] or "")) or \
                any(p.startswith(pre) and re.search(r"(^|/)test_[^/]+\.py$|_test\.py$", p) for p in test_files):
            venv = any(os.path.isdir(os.path.join(full, v)) for v in (".venv", "venv", "env"))
            res.update(command="python -m pytest -q", cwd=d or ".", deps_installed=venv or None,
                       note="Uses the active Python; activate the project's virtualenv if it has one.")
            return res
        if os.path.exists(os.path.join(full, "go.mod")) and any(p.endswith("_test.go") for p in test_files):
            res.update(command="go test ./...", cwd=d or ".", deps_installed=True)
            return res
        for f, cmd in (("pom.xml", "mvn -q test"), ("build.gradle", "gradle test"), ("build.gradle.kts", "gradle test"),
                       ("Cargo.toml", "cargo test"), ("Gemfile", "bundle exec rspec" if os.path.isdir(os.path.join(full, "spec")) else "bundle exec rails test")):
            if os.path.exists(os.path.join(full, f)) and test_files:
                res.update(command=cmd, cwd=d or ".")
                return res
        if os.path.exists(os.path.join(full, "composer.json")) and test_files:
            res.update(command="vendor/bin/phpunit", cwd=d or ".", deps_installed=os.path.isdir(os.path.join(full, "vendor")))
            return res
        if any(n.endswith(".csproj") or n.endswith(".sln") for n in os.listdir(full)) and test_files:
            res.update(command="dotnet test", cwd=d or ".")
            return res
    return res

# --------------------------------------------------------------------------- secrets

SECRET_FILE = re.compile(r"(^|/)(\.env(\.[\w-]+)?|[^/]*\.pem|[^/]*\.key|[^/]*\.p12|[^/]*\.pfx|id_rsa[^/]*|id_ed25519[^/]*|"
                         r"credentials\.json|service-?account[^/]*\.json|firebase-adminsdk[^/]*\.json|\.npmrc|\.pypirc|secrets?\.(json|ya?ml|toml))$", re.I)
SECRET_FILE_OK = re.compile(r"\.(example|sample|template|dist|defaults?)$|\.env\.(test|ci)\.example$", re.I)
HISTORY_RX = r"AKIA[0-9A-Z]{16}|[sr]k_live_[0-9A-Za-z]{16}|gh[pousr]_[A-Za-z0-9]{30}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AIza[0-9A-Za-z_-]{35}|xox[abprs]-|(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^:/ ]+:[^@ ]+@"


def scan_secrets(root, is_repo, api_files, extra_files):
    out = {"tracked_secret_files": [], "history_secret_files": [], "history_secret_commits": [], "source_hits": [], "frontend_env": []}
    if is_repo:
        code, txt = C.git(root, "ls-files")
        if code == 0:
            for p in txt.splitlines():
                if SECRET_FILE.search(p) and not SECRET_FILE_OK.search(p):
                    out["tracked_secret_files"].append(p)
        code, txt = C.git(root, "log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:@@%h %ad", "--date=short", timeout=90)
        if code == 0:
            cur = None
            tracked = set(out["tracked_secret_files"])
            for line in txt.splitlines():
                if line.startswith("@@"):
                    cur = line[2:]
                elif line.strip() and SECRET_FILE.search(line.strip()) and not SECRET_FILE_OK.search(line.strip()):
                    out["history_secret_files"].append({"path": line.strip(), "added_in": cur, "still_tracked": line.strip() in tracked})
        code, txt = C.git(root, "log", "--all", "-E", f"-G{HISTORY_RX}", "--pretty=format:%h %ad %s", "--date=short", "-n", "30", timeout=120)
        if code == 0 and txt.strip():
            out["history_secret_commits"] = txt.strip().splitlines()[:30]
    for role, files in (("api", api_files), ("extra", extra_files)):
        for p, text in files:
            quoted = not (p.rsplit("/", 1)[-1].startswith(".env") or p.endswith((".yml", ".yaml", ".properties", ".toml", ".conf")))
            for i, line in enumerate(text.splitlines(), 1):
                if len(line) > 1000:
                    continue
                for kind, preview in C.find_secrets(line, quoted_only=quoted):
                    out["source_hits"].append({"file": p, "line": i, "kind": kind, "preview": preview, "role": role})
                if role == "extra" and EXTRA_HOT["frontend_env"].search(line):
                    out["frontend_env"].append({"file": p, "line": i, "var": EXTRA_HOT["frontend_env"].search(line).group(0)})
    for p in out["tracked_secret_files"]:
        t, _ = C.read_text(os.path.join(root, p))
        if t:
            for i, line in enumerate(t.splitlines(), 1):
                for kind, preview in C.find_secrets(line, quoted_only=False):
                    out["source_hits"].append({"file": p, "line": i, "kind": kind, "preview": preview, "role": "tracked_secret_file"})
    seen, uniq = set(), []
    for h in out["source_hits"]:  # one hit per line; the first (most specific) pattern wins
        if (h["file"], h["line"]) not in seen:
            seen.add((h["file"], h["line"]))
            uniq.append(h)
    out["source_hits"] = uniq[:200]
    return out

# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--api", required=True)
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    api = C.rel(os.path.abspath(a.api), root)
    if not os.path.isdir(os.path.join(root, api)):
        print(json.dumps({"error": f"API path not found: {a.api}"}))
        return 2
    extras = []
    for e in a.extra:
        if os.path.exists(e):
            extras.append(C.rel(os.path.abspath(e), root))
    code, _ = C.git(root, "rev-parse", "--is-inside-work-tree")
    is_repo = code == 0
    commit = C.git(root, "rev-parse", "--short", "HEAD")[1].strip() if is_repo else None
    dirty = bool(C.git(root, "status", "--porcelain", "--", api)[1].strip()) if is_repo else None

    api_all = list_files(root, api, is_repo)
    files, langs, texts = {}, {}, {}
    hotspots = {k: {} for k in H}
    for p in sorted(api_all):
        lang = wanted(p)
        if not lang:
            continue
        text, b = C.read_text(os.path.join(root, p))
        if text is None:
            continue
        lines = text.splitlines()
        is_test = C.is_test_path(p)
        files[p] = {"sha256": C.sha256_bytes(b), "lines": len(lines), "lang": lang, "tokens": len(b) // 4, "role": "api"}
        if is_test:
            files[p]["test"] = True
        texts[p] = text
        if lang not in ("config",):
            langs[lang] = langs.get(lang, 0) + 1
        if is_test:
            continue
        for k, rx in HOT.items():
            hits = [i for i, line in enumerate(lines, 1) if len(line) < 2000 and rx.search(line)]
            if hits:
                hotspots[k][p] = hits[:MAX_HITS_PER_FILE]
    known = set(files)
    py_roots = sorted({api, ""} | {os.path.dirname(api)})
    for p, meta in files.items():
        if meta["lang"] in ("javascript", "typescript", "vue", "svelte"):
            imps = {resolve_js(p, s, known) for s in JS_IMPORT.findall(texts[p])}
            imps.discard(None)
            if imps:
                meta["imports"] = sorted(imps)
        elif meta["lang"] == "python":
            imps = resolve_py(p, texts[p], known, py_roots)
            if imps:
                meta["imports"] = imps

    extra_files, extra_hot = {}, {k: {} for k in EXTRA_H}
    extra_texts = []
    for e in extras:
        for p in sorted(list_files(root, e, is_repo) if os.path.isdir(os.path.join(root, e)) else [e]):
            if p in files:
                continue
            name = p.rsplit("/", 1)[-1]
            lang = wanted(p) or ("env" if name.startswith(".env") else None)
            if not lang:
                continue
            text, b = C.read_text(os.path.join(root, p))
            if text is None:
                continue
            extra_files[p] = {"sha256": C.sha256_bytes(b), "lines": text.count("\n") + 1, "lang": lang, "tokens": len(b) // 4, "role": "extra"}
            extra_texts.append((p, text))
            if C.is_test_path(p):
                continue
            for k, rx in EXTRA_HOT.items():
                hits = [i for i, line in enumerate(text.splitlines(), 1) if len(line) < 2000 and rx.search(line)]
                if hits:
                    extra_hot[k][p] = hits[:MAX_HITS_PER_FILE]

    all_repo_files = list_files(root, ".", is_repo) if is_repo else api_all
    deps, manifests = collect_dependencies(root, api, [p for p in all_repo_files if "/" not in p or p.startswith(api)])
    secrets = scan_secrets(root, is_repo, [(p, t) for p, t in texts.items() if not files[p].get("test")], extra_texts)
    hotspots["secrets"] = {}
    for h in secrets["source_hits"]:
        if h["role"] == "api":
            hotspots["secrets"].setdefault(h["file"], []).append(h["line"])
    extra_hot["secrets"] = {}
    for h in secrets["source_hits"]:
        if h["role"] == "extra":
            extra_hot["secrets"].setdefault(h["file"], []).append(h["line"])

    index = {
        "generated_at": C.now_iso(),
        "root": root,
        "api_path": api,
        "extra_paths": extras,
        "git": {"is_repo": is_repo, "commit": commit, "dirty": dirty},
        "stack": detect_stack(deps, langs),
        "runtime": detect_runtime(root, api, api_all + [m["path"] for m in manifests]),
        "tests": detect_tests(root, api, api_all),
        "files": files,
        "extra_files": extra_files,
        "manifests": manifests,
        "dependencies": deps,
        "hotspots": {k: v for k, v in hotspots.items() if v},
        "extra_hotspots": {k: v for k, v in extra_hot.items() if v},
        "secrets": secrets,
        "totals": {"files": len(files), "source_files": sum(1 for f in files.values() if not f.get("test")),
                   "lines": sum(f["lines"] for f in files.values()), "tokens": sum(f["tokens"] for f in files.values() if not f.get("test")),
                   "extra_files": len(extra_files), "dependencies": len(deps)},
    }
    C.save_json(C.state_path(root, "index.json"), index)
    st = index["stack"]
    summary = {
        "index": C.rel(C.state_path(root, "index.json"), root),
        "api_path": api, "extra_paths": extras, "commit": commit,
        "languages": langs,
        "frameworks": [f"{f['name']} {f['version']}" for f in st["frameworks"]],
        "data": [f"{f['name']} {f['version']}" for f in st["data"]],
        "runtime": [f"{r['product']} {r['version']} ({r['source']})" for r in index["runtime"]],
        "tests": index["tests"],
        "totals": index["totals"],
        "secrets": {"tracked_secret_files": secrets["tracked_secret_files"], "history_secret_files": len(secrets["history_secret_files"]),
                    "history_secret_commits": len(secrets["history_secret_commits"]), "source_hits": len(secrets["source_hits"]),
                    "frontend_env": len(secrets["frontend_env"])},
        "hotspot_files": {k: len(v) for k, v in index["hotspots"].items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
