"""Detect the backend's stack, test runner, full-suite command, test DB and external services.

Writes qa/env.json and prints a short summary. Never prints secret values: env files are read
for key names and a few booleans (is TEST_DATABASE_URL set, does it differ from DATABASE_URL,
is it local, does the DB name contain "test", are payment keys test-mode or live).

Usage: python detect_env.py --root . [--src api/] [--no-docker]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

SRC_CANDIDATES = ["api", "server", "backend", "apps/api", "apps/server", "apps/backend",
                  "packages/api", "packages/server", "services/api", "src", "app", "cmd", "internal"]
ENV_FILES = [".env", ".env.local", ".env.development", ".env.development.local", ".env.test",
             ".env.test.local", ".env.example", ".env.test.example", ".env.sample"]

FRAMEWORKS = {
    # js/ts
    "express": "express", "fastify": "fastify", "hono": "hono", "@nestjs/core": "nestjs", "koa": "koa",
    "elysia": "elysia", "@hapi/hapi": "hapi", "next": "nextjs-api", "@trpc/server": "trpc",
    "apollo-server": "apollo", "@apollo/server": "apollo", "graphql-yoga": "graphql-yoga",
    # python
    "fastapi": "fastapi", "django": "django", "djangorestframework": "drf", "flask": "flask",
    "starlette": "starlette", "litestar": "litestar", "sanic": "sanic", "aiohttp": "aiohttp",
    # go
    "github.com/gin-gonic/gin": "gin", "github.com/labstack/echo": "echo", "github.com/gofiber/fiber": "fiber",
    "github.com/go-chi/chi": "chi", "github.com/gorilla/mux": "gorilla",
    # others
    "spring-boot-starter-web": "spring", "laravel/framework": "laravel", "rails": "rails", "sinatra": "sinatra",
    "actix-web": "actix", "axum": "axum", "rocket": "rocket",
}
TEST_RUNNERS_JS = ["vitest", "jest", "mocha", "ava", "tap", "@japa/runner", "uvu"]
DB_DEPS = {
    "pg": "postgres", "postgres": "postgres", "@neondatabase/serverless": "postgres", "psycopg": "postgres",
    "psycopg2": "postgres", "psycopg2-binary": "postgres", "asyncpg": "postgres", "github.com/jackc/pgx": "postgres",
    "github.com/lib/pq": "postgres", "mysql2": "mysql", "mysql": "mysql", "pymysql": "mysql", "mysqlclient": "mysql",
    "github.com/go-sql-driver/mysql": "mysql", "mongoose": "mongodb", "mongodb": "mongodb", "pymongo": "mongodb",
    "motor": "mongodb", "go.mongodb.org/mongo-driver": "mongodb", "better-sqlite3": "sqlite", "sqlite3": "sqlite",
    "@libsql/client": "sqlite", "aiosqlite": "sqlite", "redis": "redis", "ioredis": "redis",
}
ORM_DEPS = {"prisma": "prisma", "@prisma/client": "prisma", "drizzle-orm": "drizzle", "typeorm": "typeorm",
            "sequelize": "sequelize", "@mikro-orm/core": "mikro-orm", "knex": "knex", "kysely": "kysely",
            "sqlalchemy": "sqlalchemy", "sqlmodel": "sqlmodel", "tortoise-orm": "tortoise", "peewee": "peewee",
            "gorm.io/gorm": "gorm", "entgo.io/ent": "ent", "github.com/jmoiron/sqlx": "sqlx", "alembic": "alembic"}
EXTERNALS = {
    "stripe": ("stripe", ["STRIPE"]), "@stripe/stripe-js": ("stripe", ["STRIPE"]), "iyzipay": ("iyzico", ["IYZI"]),
    "@paypal/checkout-server-sdk": ("paypal", ["PAYPAL"]), "paypalrestsdk": ("paypal", ["PAYPAL"]),
    "braintree": ("braintree", ["BRAINTREE"]), "@paddle/paddle-node-sdk": ("paddle", ["PADDLE"]),
    "@lemonsqueezy/lemonsqueezy.js": ("lemonsqueezy", ["LEMON"]),
    "nodemailer": ("smtp", ["SMTP", "MAIL"]), "resend": ("resend", ["RESEND"]), "@sendgrid/mail": ("sendgrid", ["SENDGRID"]),
    "postmark": ("postmark", ["POSTMARK"]), "mailgun.js": ("mailgun", ["MAILGUN"]), "twilio": ("twilio", ["TWILIO"]),
    "@aws-sdk/client-s3": ("s3", ["AWS", "S3"]), "aws-sdk": ("aws", ["AWS"]), "boto3": ("aws", ["AWS"]),
    "@google-cloud/storage": ("gcs", ["GOOGLE", "GCS", "GCP"]), "cloudinary": ("cloudinary", ["CLOUDINARY"]),
    "firebase-admin": ("firebase", ["FIREBASE"]), "openai": ("openai", ["OPENAI"]),
    "@anthropic-ai/sdk": ("anthropic", ["ANTHROPIC"]), "anthropic": ("anthropic", ["ANTHROPIC"]),
    "passport-google-oauth20": ("google-oauth", ["GOOGLE"]), "@auth/core": ("oauth", ["AUTH_"]),
    "next-auth": ("oauth", ["NEXTAUTH", "AUTH_"]), "@clerk/backend": ("clerk", ["CLERK"]),
    "@supabase/supabase-js": ("supabase", ["SUPABASE"]), "pusher": ("pusher", ["PUSHER"]),
    "github.com/stripe/stripe-go": ("stripe", ["STRIPE"]),
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "db", "postgres", "mysql", "mongo", "mongodb",
               "database", "host.docker.internal", "redis"}


def run(cmd, cwd, timeout=10):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def pick_src(root, given):
    if given:
        return [given.rstrip("/\\")]
    for c in SRC_CANDIDATES:
        p = os.path.join(root, c)
        if os.path.isdir(p) and any(True for _ in C.walk_code(root, [c])):
            return [c]
    return ["."]


def load_toml(path):
    text = C.read_text(path)
    if text is None:
        return None, ""
    try:
        import tomllib  # py3.11+
        return tomllib.loads(text), text
    except Exception:  # noqa: BLE001 (old python or invalid toml): regex fallback below
        return None, text


def deps_from_pyproject(data, text):
    names = set()
    if data:
        proj = data.get("project", {})
        for d in proj.get("dependencies", []) or []:
            names.add(re.split(r"[\s<>=!~\[;]", d, 1)[0].lower())
        for grp in (proj.get("optional-dependencies") or {}).values():
            for d in grp:
                names.add(re.split(r"[\s<>=!~\[;]", d, 1)[0].lower())
        for grp in (data.get("dependency-groups") or {}).values():
            for d in grp:
                if isinstance(d, str):
                    names.add(re.split(r"[\s<>=!~\[;]", d, 1)[0].lower())
        poetry = data.get("tool", {}).get("poetry", {})
        for key in ("dependencies", "dev-dependencies"):
            names.update(k.lower() for k in (poetry.get(key) or {}))
        for grp in (poetry.get("group") or {}).values():
            names.update(k.lower() for k in (grp.get("dependencies") or {}))
    else:
        names.update(m.lower() for m in re.findall(r"^\s*['\"]?([A-Za-z0-9_.-]+)\s*[<>=~!\[\"']", text, re.M))
    return names


def find_manifest_dirs(root, src):
    dirs = []
    for d in [src, "."]:
        p = os.path.normpath(os.path.join(root, d))
        while True:
            if p not in dirs:
                dirs.append(p)
            if os.path.normpath(p) == os.path.normpath(root) or not p.startswith(os.path.normpath(root)):
                break
            p = os.path.dirname(p)
    return dirs


def detect(root, src_dirs, check_docker=True):
    src = src_dirs[0]
    out = {"root": root, "src": src_dirs, "ecosystem": None, "package_manager": None, "frameworks": [],
           "orm": [], "db_engine": None, "test_runner": None, "test_runner_installed": False,
           "test_script": None, "suggested_test_command": None, "manifest": None, "existing_tests": {},
           "test_db": {}, "externals": [], "docker": None, "security_report": None, "claude_version": None,
           "env_files": [], "notes": []}
    deps = set()
    dev_deps = set()

    for d in find_manifest_dirs(root, src):
        relp = C.rel(d, root)
        pj = os.path.join(d, "package.json")
        if os.path.exists(pj) and not out["ecosystem"]:
            data = C.load_json(pj, {}) or {}
            deps.update((data.get("dependencies") or {}).keys())
            dev_deps.update((data.get("devDependencies") or {}).keys())
            out["ecosystem"] = "node"
            out["manifest"] = C.rel(pj, root)
            pm = (data.get("packageManager") or "").split("@")[0] or None
            for lock, name in (("bun.lockb", "bun"), ("bun.lock", "bun"), ("pnpm-lock.yaml", "pnpm"),
                               ("yarn.lock", "yarn"), ("package-lock.json", "npm")):
                if pm:
                    break
                for ld in (d, root):
                    if os.path.exists(os.path.join(ld, lock)):
                        pm = name
                        break
            out["package_manager"] = pm or "npm"
            if out["package_manager"] == "bun":
                out["ecosystem"] = "bun"
            scripts = data.get("scripts") or {}
            out["test_script"] = scripts.get("test")
            out["scripts"] = {k: v for k, v in scripts.items() if k.startswith("test") or k in ("build", "dev", "start")}
            alld = deps | dev_deps
            runner = next((r for r in TEST_RUNNERS_JS if r in alld), None)
            if not runner and out["test_script"]:
                ts = out["test_script"]
                runner = next((r for r in ["vitest", "jest", "mocha", "bun test", "node --test", "ava", "tap"] if r in ts), None)
            if not runner:
                runner = "bun test" if out["package_manager"] == "bun" else "vitest"
                out["notes"].append(f"No JS test runner found; default would be {runner}.")
            else:
                out["test_runner_installed"] = True
            out["test_runner"] = runner
            pmcmd = {"bun": "bun run test", "pnpm": "pnpm test", "yarn": "yarn test"}.get(out["package_manager"], "npm test")
            out["suggested_test_command"] = pmcmd if relp in (".", "") else f"cd {relp} && {pmcmd}"
            if os.path.exists(os.path.join(d, "deno.json")):
                out["notes"].append("deno.json present too")
        if os.path.exists(os.path.join(d, "deno.json")) and not out["ecosystem"]:
            out.update(ecosystem="deno", package_manager="deno", manifest=C.rel(os.path.join(d, "deno.json"), root),
                       test_runner="deno test", suggested_test_command="deno task test")
        pp = os.path.join(d, "pyproject.toml")
        reqs = [f for f in ("requirements.txt", "requirements-dev.txt", "requirements/dev.txt", "requirements/base.txt")
                if os.path.exists(os.path.join(d, f))]
        if (os.path.exists(pp) or reqs) and not out["ecosystem"]:
            out["ecosystem"] = "python"
            if os.path.exists(pp):
                data, text = load_toml(pp)
                deps.update(deps_from_pyproject(data, text))
                out["manifest"] = C.rel(pp, root)
                if data and "pytest" in json.dumps(data.get("tool", {}).get("pytest", {})) or "[tool.pytest" in (text or ""):
                    out["test_runner_installed"] = True
            for r in reqs:
                for line in (C.read_text(os.path.join(d, r)) or "").splitlines():
                    m = re.match(r"^\s*([A-Za-z0-9_.-]+)", line)
                    if m:
                        deps.add(m.group(1).lower())
                out["manifest"] = out["manifest"] or C.rel(os.path.join(d, r), root)
            pm = "uv" if os.path.exists(os.path.join(d, "uv.lock")) else "poetry" if os.path.exists(os.path.join(d, "poetry.lock")) \
                else "pdm" if os.path.exists(os.path.join(d, "pdm.lock")) else "pip"
            out["package_manager"] = pm
            out["test_runner"] = "pytest" if "pytest" in deps or not any(x in deps for x in ("nose2",)) else "unittest"
            out["test_runner_installed"] = out["test_runner_installed"] or "pytest" in deps
            out["suggested_test_command"] = {"uv": "uv run pytest", "poetry": "poetry run pytest",
                                             "pdm": "pdm run pytest"}.get(pm, "pytest")
            if "django" in deps and not any(x in deps for x in ("pytest-django",)):
                out["notes"].append("Django without pytest-django: add it as a dev dependency or use manage.py test.")
        gm = os.path.join(d, "go.mod")
        if os.path.exists(gm) and not out["ecosystem"]:
            text = C.read_text(gm) or ""
            deps.update(re.findall(r"^\s*(?:require\s+)?([a-z0-9.\-]+\.[a-z]+/[^\s]+)\s+v", text, re.M))
            out.update(ecosystem="go", package_manager="go", manifest=C.rel(gm, root), test_runner="go test",
                       test_runner_installed=True, suggested_test_command="go test ./...")
        for name, eco, pm, runner, cmd in (("pom.xml", "java", "maven", "junit", "mvn test"),
                                            ("build.gradle", "java", "gradle", "junit", "./gradlew test"),
                                            ("build.gradle.kts", "kotlin", "gradle", "junit", "./gradlew test"),
                                            ("composer.json", "php", "composer", "phpunit", "composer test"),
                                            ("Gemfile", "ruby", "bundler", "rspec", "bundle exec rspec"),
                                            ("Cargo.toml", "rust", "cargo", "cargo test", "cargo test")):
            p = os.path.join(d, name)
            if os.path.exists(p) and not out["ecosystem"]:
                text = C.read_text(p) or ""
                out.update(ecosystem=eco, package_manager=pm, manifest=C.rel(p, root), test_runner=runner,
                           suggested_test_command=cmd)
                deps.update(re.findall(r"<artifactId>([^<]+)</artifactId>", text))
                deps.update(re.findall(r"['\"]([a-z0-9_\-]+/[a-z0-9_\-]+)['\"]\s*:", text))  # composer
                deps.update(re.findall(r"^\s*gem\s+['\"]([^'\"]+)", text, re.M))
                deps.update(re.findall(r"^\s*([a-z0-9_\-]+)\s*=", text, re.M))  # cargo
                if name == "composer.json":
                    cj = C.load_json(p, {}) or {}
                    out["test_script"] = (cj.get("scripts") or {}).get("test")
                    if "phpunit/phpunit" in (cj.get("require-dev") or {}) or "pestphp/pest" in (cj.get("require-dev") or {}):
                        out["test_runner_installed"] = True
                        out["test_runner"] = "pest" if "pestphp/pest" in (cj.get("require-dev") or {}) else "phpunit"
                if name == "Gemfile" and "rspec" not in text:
                    out["test_runner"] = "minitest"
                    out["suggested_test_command"] = "bundle exec rake test"
        if not out["ecosystem"]:
            for f in os.listdir(d) if os.path.isdir(d) else []:
                if f.endswith((".csproj", ".sln")):
                    out.update(ecosystem="csharp", package_manager="dotnet", manifest=C.rel(os.path.join(d, f), root),
                               test_runner="xunit", suggested_test_command="dotnet test")
                    deps.update(re.findall(r'Include="([^"]+)"', C.read_text(os.path.join(d, f)) or ""))
                    break

    alld = {x.lower() for x in deps | dev_deps}
    out["frameworks"] = sorted({v for k, v in FRAMEWORKS.items() if k.lower() in alld or any(a.startswith(k.lower()) for a in alld if "/" in k)})
    out["orm"] = sorted({v for k, v in ORM_DEPS.items() if k.lower() in alld or any(a.startswith(k.lower()) for a in alld if "/" in k)})
    engines = sorted({v for k, v in DB_DEPS.items() if k.lower() in alld or any(a.startswith(k.lower()) for a in alld if "/" in k)} - {"redis"})
    if not engines:
        for schema in ("prisma/schema.prisma", f"{src}/prisma/schema.prisma"):
            t = C.read_text(os.path.join(root, schema)) or ""
            m = re.search(r'provider\s*=\s*"(postgresql|mysql|sqlite|mongodb|sqlserver|cockroachdb)"', t)
            if m:
                engines = [{"postgresql": "postgres", "cockroachdb": "postgres"}.get(m.group(1), m.group(1))]
                break
    out["db_engines_from_deps"] = engines
    out["uses_redis"] = any(x in alld for x in ("redis", "ioredis", "bullmq", "celery", "rq"))
    out["dev_deps_present"] = sorted(x for x in alld if x in {
        "supertest", "msw", "nock", "testcontainers", "@testcontainers/postgresql", "pg-mem", "@electric-sql/pglite",
        "mongodb-memory-server", "jest-junit", "@vitest/coverage-v8", "@vitest/coverage-istanbul", "c8",
        "pytest-cov", "pytest-asyncio", "httpx", "respx", "responses", "freezegun", "time-machine", "factory-boy",
        "testcontainers-python", "pytest-django", "moto", "faker", "@faker-js/faker", "gotestsum",
        "github.com/stretchr/testify", "github.com/testcontainers/testcontainers-go"})

    # ---------------------------------------------------------------- existing tests
    test_files = []
    for rp, _lang in C.walk_code(root, ["."], include_tests=True):
        if C.TEST_PATH.search(rp) and not re.search(r"(^|/)(fixtures?|mocks?|__mocks__)/", rp):
            test_files.append(rp)
    top = {}
    for t in test_files:
        top_dir = t.split("/")[0] if "/" in t else "."
        top[top_dir] = top.get(top_dir, 0) + 1
    out["existing_tests"] = {"count": len(test_files), "by_top_dir": dict(sorted(top.items(), key=lambda x: -x[1])[:8]),
                             "examples": test_files[:5]}

    # ---------------------------------------------------------------- env files (key names only)
    env_vals = {}
    for d in dict.fromkeys([root, os.path.join(root, src)]):
        for f in ENV_FILES:
            p = os.path.join(d, f)
            if os.path.isfile(p):
                vals = C.parse_env_file(p)
                relp = C.rel(p, root)
                out["env_files"].append({"file": relp, "keys": sorted(vals.keys())})
                for k, v in vals.items():
                    env_vals.setdefault(k, []).append((relp, v))

    def first_real(key):
        """(file, value) for key, preferring test files, skipping *.example placeholders."""
        cands = list(env_vals.get(key, []))
        if os.environ.get(key):
            cands.insert(0, ("(process env)", os.environ[key]))
        real = [c for c in cands if "example" not in c[0] and "sample" not in c[0] and c[1]]
        real.sort(key=lambda c: 0 if ".test" in c[0] else 1)
        return real[0] if real else (None, None)

    tdb_file, tdb = first_real("TEST_DATABASE_URL")
    db_candidates = [c for c in env_vals.get("DATABASE_URL", []) if ".test" not in c[0] and "example" not in c[0]]
    if os.environ.get("DATABASE_URL"):
        db_candidates.append(("(process env)", os.environ["DATABASE_URL"]))
    dbs = {v for _f, v in db_candidates if v}
    test_db = {"found": bool(tdb), "where": tdb_file, "scheme": None, "differs_from_database_url": None,
               "local_host": None, "name_has_test": None, "safe": False}
    engine_url = tdb or (next(iter(dbs)) if dbs else None)
    if tdb:
        try:
            u = urlparse(tdb)
            test_db["scheme"] = u.scheme
            host = (u.hostname or "").lower()
            test_db["local_host"] = host in LOCAL_HOSTS or host.endswith(".local") or host.endswith(".localhost") or u.scheme.startswith("sqlite") or tdb.startswith("file:")
            name = (u.path or "").strip("/").lower()
            test_db["name_has_test"] = "test" in name or "test" in host
        except ValueError:
            pass
        test_db["differs_from_database_url"] = tdb not in dbs
        test_db["safe"] = bool(test_db["differs_from_database_url"] and (test_db["local_host"] or test_db["name_has_test"]))
    out["test_db"] = test_db
    scheme_engine = None
    if engine_url:
        s = engine_url.split(":", 1)[0].lower()
        scheme_engine = {"postgres": "postgres", "postgresql": "postgres", "mysql": "mysql", "mariadb": "mysql",
                         "mongodb": "mongodb", "mongodb+srv": "mongodb", "sqlite": "sqlite", "file": "sqlite",
                         "sqlserver": "sqlserver", "mssql": "sqlserver"}.get(s.split("+")[0] if s != "mongodb+srv" else s)
    out["db_engine"] = scheme_engine or (engines[0] if engines else None)

    # ---------------------------------------------------------------- externals
    seen = {}
    for dep, (svc, prefixes) in EXTERNALS.items():
        if dep.lower() in alld or any(a.startswith(dep.lower()) for a in alld if "/" in dep):
            seen.setdefault(svc, set()).update(prefixes)
    for svc, prefixes in sorted(seen.items()):
        keys = sorted({k for k in env_vals if any(k.upper().startswith(p) or p in k.upper() for p in prefixes)})
        mode = "none"
        for k in keys:
            f, v = first_real(k)
            if not v:
                continue
            vl = v.lower()
            if re.match(r"^(sk|pk|rk)_live_", v) or "live" in k.lower():
                mode = "live"
                break
            if re.match(r"^(sk|pk|rk)_test_", v) or "sandbox" in vl or "sandbox" in k.lower() or "test" in k.lower() \
                    or re.search(r"(?i)sandbox|\.test\b|test-?mode", vl):
                mode = "sandbox"
            elif mode == "none":
                mode = "unknown"
        out["externals"].append({"service": svc, "keys_found": keys, "mode": mode,
                                 "use": "sandbox" if mode == "sandbox" else "mock"})

    # ---------------------------------------------------------------- tools
    if check_docker and shutil.which("docker"):
        code, _ = run(["docker", "info", "--format", "{{.ServerVersion}}"], root, timeout=12)
        out["docker"] = code == 0
    else:
        out["docker"] = False if check_docker else None
    sp = os.path.join(root, "docs", "SECURITY_PROBLEMS.md")
    out["security_report"] = C.rel(sp, root) if os.path.exists(sp) else None
    if shutil.which("claude"):
        try:
            exe, _shim = C.claude_command()
        except SystemExit:
            exe = None
        _c, v = run(exe + ["--version"], root, timeout=30) if exe else (None, "")
        m = re.search(r"(\d+\.\d+\.\d+)", v or "")
        out["claude_version"] = m.group(1) if m else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--src")
    ap.add_argument("--no-docker", action="store_true", help="skip the docker check")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    src = pick_src(root, a.src)
    env = detect(root, src, check_docker=not a.no_docker)
    C.save_json(C.qa_path(root, "env.json"), env)
    tdb = env["test_db"]
    lines = [
        f"src: {', '.join(env['src'])} · ecosystem: {env['ecosystem']} · package manager: {env['package_manager']}",
        f"frameworks: {', '.join(env['frameworks']) or '-'} · orm: {', '.join(env['orm']) or '-'} · db: {env['db_engine'] or '-'}",
        f"test runner: {env['test_runner']} (installed: {env['test_runner_installed']}) · test script: {env['test_script'] or '-'}",
        f"full-suite command: {env['suggested_test_command']}",
        f"existing tests: {env['existing_tests']['count']} files {env['existing_tests']['by_top_dir']}",
        "TEST_DATABASE_URL: " + (f"found in {tdb['where']} · scheme {tdb['scheme']} · differs from DATABASE_URL: "
                                 f"{tdb['differs_from_database_url']} · local: {tdb['local_host']} · name has 'test': "
                                 f"{tdb['name_has_test']} · safe: {tdb['safe']}" if tdb["found"] else "not found"),
        "externals: " + (", ".join(f"{x['service']}={x['mode']}->{x['use']}" for x in env["externals"]) or "-"),
        f"docker: {env['docker']} · security report: {env['security_report'] or '-'} · claude: {env['claude_version'] or 'not found'}",
    ]
    for n in env["notes"]:
        lines.append(f"note: {n}")
    lines.append("written: qa/env.json")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
