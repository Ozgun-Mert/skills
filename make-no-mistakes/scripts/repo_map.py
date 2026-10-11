"""Build mnm/repo-map.md: the one compact map of an existing repo that the whole run starts from.

One pass, no LLM: packages and detected stack (from manifests), scripts/commands, directory tree
with file and line counts, frontend pages/routes, backend API routes, data models, auth-related
files, tests and env variables. The orchestrator reads this file instead of browsing the repo.

Usage: python repo_map.py --root . [--max-items 80]
Prints a short summary; the full map goes to mnm/repo-map.md (and mnm/repo-map.json).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

EXCLUDE_DIRS = {
    "node_modules", "vendor", ".venv", "venv", "env", "dist", "build", "out", ".next", ".nuxt",
    "coverage", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "target",
    "bin", "obj", ".turbo", ".cache", ".idea", ".vscode", ".svelte-kit", "mnm", ".output",
    "playwright-report", "test-results", ".vercel",
}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".svelte", ".vue", ".rb",
            ".php", ".java", ".kt", ".cs", ".rs", ".sql", ".prisma", ".astro", ".css", ".scss",
            ".html", ".md", ".mdx", ".yaml", ".yml", ".toml", ".json"}
MANIFESTS = {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml",
             "composer.json", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "deno.json"}

STACK_HINTS = {
    # npm
    "next": "Next.js", "@sveltejs/kit": "SvelteKit", "nuxt": "Nuxt", "astro": "Astro",
    "@remix-run/react": "Remix", "react-router": "React Router", "vite": "Vite", "react": "React",
    "vue": "Vue", "svelte": "Svelte", "express": "Express", "hono": "Hono", "fastify": "Fastify",
    "@nestjs/core": "NestJS", "elysia": "Elysia", "koa": "Koa", "prisma": "Prisma",
    "@prisma/client": "Prisma", "drizzle-orm": "Drizzle", "typeorm": "TypeORM", "sequelize": "Sequelize",
    "mongoose": "Mongoose", "zod": "Zod", "tailwindcss": "Tailwind", "@playwright/test": "Playwright",
    "vitest": "Vitest", "jest": "Jest", "better-auth": "Better Auth", "next-auth": "NextAuth",
    "lucia": "Lucia", "@supabase/supabase-js": "Supabase", "firebase": "Firebase",
    # python
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic", "pydantic": "Pydantic", "pytest": "pytest", "sqlmodel": "SQLModel",
    "celery": "Celery",
    # go
    "github.com/go-chi/chi": "chi", "github.com/gin-gonic/gin": "Gin", "github.com/labstack/echo": "Echo",
    "github.com/gofiber/fiber": "Fiber", "github.com/jackc/pgx": "pgx", "gorm.io/gorm": "GORM",
    "github.com/pressly/goose": "goose", "github.com/sqlc-dev": "sqlc",
}

ROUTE_RX = re.compile(
    r"\b(app|router|server|api|route|r|e|g|mux|v1|group|\w+Router|\w+Routes)\.(get|post|put|patch|delete|all|route|HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)"
    r"\s*\(\s*[`'\"]((GET|POST|PUT|PATCH|DELETE)\s+)?/|"
    r"@(app|router|api|bp)\.(get|post|put|patch|delete|route|api_route|websocket)\s*\(|"
    r"@(Get|Post|Put|Patch|Delete)\s*\(|\bpath\s*\(\s*r?['\"]|export\s+(async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b|"
    r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\b|export\s+const\s+actions\b")
MODEL_RX = re.compile(
    r"class\s+\w+\s*\((Base|DeclarativeBase|SQLModel|models\.Model|db\.Model)[^)]*\)|"
    r"\b(pgTable|sqliteTable|mysqlTable)\s*\(\s*['\"]\w+|^\s*model\s+\w+\s*\{|"
    r"(?i:create\s+table\s+(if\s+not\s+exists\s+)?[\"`]?\w+)|type\s+\w+\s+struct\s*\{[^}]*`db:|"
    r"new\s+(mongoose\.)?Schema\s*\(|@Entity\s*\(", re.M)
AUTH_RX = re.compile(r"(?i)\b(jwt|jsonwebtoken|passport|bcrypt|argon2|session|authenticat|authoriz|"
                     r"current_user|get_current_user|req\.user|requireAuth|login_required|Depends\(|"
                     r"getServerSession|auth\(\)|middleware|guard|lucia|better-auth|next-auth)\b")
ENV_RX = re.compile(r"(process\.env\.|import\.meta\.env\.|os\.environ(?:\.get)?\(?\[?['\"]|os\.getenv\(['\"]|"
                    r"Getenv\(\")([A-Z][A-Z0-9_]{2,})")
TEST_RX = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$|_test\.go$")
PAGE_RX = re.compile(r"(^|/)(app|src/app)/(.*/)?(page|layout|route)\.(tsx|ts|jsx|js|mdx)$|"
                     r"(^|/)(pages|src/pages)/.+\.(tsx|jsx|js|ts|vue|astro|md|mdx)$|"
                     r"(^|/)src/routes/(.*/)?\+(page|layout|server|page\.server|layout\.server)\.(svelte|ts|js)$")


def git_files(root):
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if r.returncode == 0:
            return [p.strip().strip('"') for p in r.stdout.splitlines() if p.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def walk_files(root):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in EXCLUDE_DIRS and not x.startswith(".")]
        for f in files:
            out.append(os.path.relpath(os.path.join(d, f), root).replace("\\", "/"))
    return out


def read(path, limit=1_500_000):
    try:
        with open(path, "rb") as f:
            b = f.read(limit + 1)
    except OSError:
        return None
    if len(b) > limit or b"\x00" in b[:4096]:
        return None
    return b.decode("utf-8", errors="replace")


def manifest_info(root, path):
    full = os.path.join(root, path)
    name = os.path.basename(path)
    txt = read(full) or ""
    deps, scripts = set(), {}
    if name == "package.json":
        try:
            pj = json.loads(txt)
        except ValueError:
            pj = {}
        for sec in ("dependencies", "devDependencies", "peerDependencies"):
            deps |= set((pj.get(sec) or {}).keys())
        scripts = pj.get("scripts") or {}
    elif name in ("pyproject.toml", "requirements.txt"):
        for m in re.finditer(r"(?im)^[\s\"']*([a-z0-9_.\-]+)(\[[^\]]*\])?\s*([<>=~!]|$|\"|,)", txt):
            deps.add(m.group(1).lower())
        for m in re.finditer(r"(?m)^\s*([\w-]+)\s*=\s*\"([^\"]+)\"", txt.split("[tool.poe.tasks]")[-1]
                             if "[tool.poe.tasks]" in txt else ""):
            scripts[m.group(1)] = m.group(2)
    elif name == "go.mod":
        for m in re.finditer(r"(?m)^\s*(?:require\s+)?([a-z0-9.\-]+\.[a-z]+/[^\s]+)\s+v", txt):
            deps.add(m.group(1))
    stack = sorted({label for key, label in STACK_HINTS.items()
                    if key in deps or any(d.startswith(key + "/") for d in deps)})
    return {"path": path, "dir": os.path.dirname(path) or ".", "stack": stack, "scripts": scripts}


def make_targets(root, files):
    out = {}
    for p in files:
        if os.path.basename(p) in ("Makefile", "justfile", "Justfile"):
            txt = read(os.path.join(root, p)) or ""
            out[p] = sorted(set(re.findall(r"(?m)^([a-zA-Z][\w-]*)\s*:(?!=)", txt)))[:30]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-items", type=int, default=80)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    N = a.max_items

    files = git_files(root) or walk_files(root)
    files = [p.replace("\\", "/") for p in files
             if not set(p.replace("\\", "/").split("/")[:-1]) & EXCLUDE_DIRS
             and os.path.isfile(os.path.join(root, p))]

    manifests = [manifest_info(root, p) for p in files
                 if os.path.basename(p) in MANIFESTS and "node_modules" not in p]
    dir_stats = defaultdict(lambda: [0, 0])  # dir -> [files, lines]
    routes, models, auth_files, envs, pages, tests = [], [], [], set(), [], []
    big_files = []

    for p in files:
        ext = os.path.splitext(p)[1].lower()
        parts = p.split("/")
        txt = read(os.path.join(root, p)) if ext in CODE_EXT else None
        lines = txt.count("\n") + 1 if txt else 0
        for depth in range(1, min(len(parts), 4)):
            d = "/".join(parts[:depth])
            dir_stats[d][0] += 1
            dir_stats[d][1] += lines
        if len(parts) == 1:
            dir_stats["."][0] += 1
            dir_stats["."][1] += lines
        if TEST_RX.search(p):
            tests.append(p)
        if PAGE_RX.search(p):
            pages.append(p)
        if not txt or ext in (".md", ".mdx", ".json", ".css", ".scss", ".html", ".yaml", ".yml", ".toml"):
            continue
        if lines > 400:
            big_files.append((lines, p))
        is_test = bool(TEST_RX.search(p))
        auth_hits = 0
        for i, line in enumerate(txt.splitlines(), 1):
            s = line.strip()
            if not is_test and ROUTE_RX.search(line) and len(routes) < N * 3:
                routes.append(f"{p}:{i}  {s[:110]}")
            if MODEL_RX.search(line) and len(models) < N * 2:
                models.append(f"{p}:{i}  {s[:110]}")
            if not is_test and AUTH_RX.search(line):
                auth_hits += 1
            for m in ENV_RX.finditer(line):
                envs.add(m.group(2))
        if auth_hits >= 3 or re.search(r"(?i)(^|/)(auth|session|security|middleware|guard)s?[\w.-]*\.", p):
            if not is_test:
                auth_files.append((auth_hits, p))

    for p in files:  # .env.example variables
        if re.search(r"(^|/)\.env\.(example|sample|template)$", p):
            for m in re.finditer(r"(?m)^\s*([A-Z][A-Z0-9_]{2,})\s*=", read(os.path.join(root, p)) or ""):
                envs.add(m.group(1))

    stack = sorted({s for m in manifests for s in m["stack"]})
    data = {
        "root": root, "files": len(files), "stack": stack, "packages": manifests,
        "make_targets": make_targets(root, files),
        "pages": pages[:N], "routes": routes[:N * 3], "models": models[:N * 2],
        "auth_files": [p for _, p in sorted(auth_files, reverse=True)[:25]],
        "tests": {"count": len(tests), "sample": tests[:15]},
        "env_vars": sorted(envs)[:N],
        "big_files": [f"{p} ({n} lines)" for n, p in sorted(big_files, reverse=True)[:15]],
    }

    out = [f"# Repo map: {os.path.basename(root)}", "",
           f"Files: {len(files)} · Stack: {', '.join(stack) or 'unknown'}", ""]
    out.append("## Packages and commands")
    for m in manifests:
        out.append(f"- `{m['path']}`: {', '.join(m['stack']) or '—'}")
        for k, v in list(m["scripts"].items())[:14]:
            out.append(f"  - `{k}`: `{v[:100]}`")
    for p, t in data["make_targets"].items():
        out.append(f"- `{p}` targets: {', '.join(t)}")
    out += ["", "## Tree (files · lines, depth ≤ 3)"]
    for d in sorted(dir_stats):
        if d == ".":
            continue
        depth = d.count("/")
        if dir_stats[d][0] < 2 and depth > 0:
            continue
        out.append(f"{'  ' * depth}- {d.split('/')[-1]}/  ({dir_stats[d][0]} · {dir_stats[d][1]})")
    for title, items in (("Frontend pages / route files", data["pages"]),
                         ("API routes (file:line)", data["routes"]),
                         ("Data models (file:line)", data["models"]),
                         ("Auth / session / middleware files", data["auth_files"]),
                         ("Large files", data["big_files"])):
        out += ["", f"## {title}"] + ([f"- {x}" for x in items] or ["- none found"])
    out += ["", f"## Tests ({len(tests)} files)"] + [f"- {x}" for x in data["tests"]["sample"]]
    out += ["", "## Env variables referenced", ", ".join(data["env_vars"]) or "none"]

    mnm = os.path.join(root, "mnm")
    os.makedirs(mnm, exist_ok=True)
    with open(os.path.join(mnm, "repo-map.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(mnm, "repo-map.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)

    print(f"repo-map: {len(files)} files · stack: {', '.join(stack) or 'unknown'} · "
          f"{len(pages)} page files · {len(routes)} route lines · {len(models)} model lines · "
          f"{len(tests)} test files → mnm/repo-map.md")


if __name__ == "__main__":
    sys.exit(main())
