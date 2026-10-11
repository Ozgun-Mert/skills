# Stack selection (Phase 3)

You choose the stack. Never ask the user to choose; the only exception is when they already named a
stack themselves. Write the choice and a one-line reason to `mnm/decisions.md`.

## 1. Backend size (score the spec, add the points)

| Signal | Points |
|---|---|
| Entities/tables in the data model: ≤ 6 → 0 · 7–15 → 2 · 16–30 → 4 · > 30 → 6 | |
| Roles beyond "user": 0 → 0 · 1–2 → 1 · ≥ 3 or per-resource permission levels → 2 | |
| Multi-tenant (organizations/teams/classes with members) | 2 |
| Payments/subscriptions | 2 |
| Realtime (websockets, live collaboration, chat) | 2 |
| Background jobs/scheduled work (emails, reminders, imports, media processing) | 1 |
| Each external integration (OAuth providers don't count) | 1 |
| Heavy compute or high throughput (media, search indexing, streaming, > 100k users expected) | 3 |
| Separate services/bounded contexts that must scale independently | 3 |

| Total | Size | Backend |
|---|---|---|
| 0–4 | **Small** | **Python + FastAPI** |
| 5–10 | **Medium** | **Bun + TypeScript** |
| ≥ 11 | **Large** | **Go** |

No backend needed at all (static content, no accounts, no stored data) → skip the backend and the
security gate's server part. Still run the frontend security checks.

## 2. Frontend size

Count distinct **page types** (a route template counts once: `/decks/[id]` is one).

| Page types and interactivity | Frontend |
|---|---|
| ≤ 8 page types and mostly forms/lists | **SvelteKit**: server rendering, readable components, small bundles, strong SEO |
| > 8 page types, or app-like UI (dashboards, editors, many nested layouts) | **Next.js** App Router |

Both render HTML on the server, which SEO needs. Never use a client-only SPA (Vite+React/Vue
without SSR) for anything with public pages.

## 3. Default stacks

### Small: FastAPI
- Python 3.12+, FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 (async, `asyncpg`),
  Alembic, `pwdlib[argon2]`, `slowapi` (rate limits), `uv` for dependencies.
- Layout: `backend/app/{main.py, config.py, db.py, deps.py, security.py, models/, schemas/, routers/, services/}`,
  `backend/tests/`, `backend/alembic/`.
- Tests: `pytest` + `httpx.AsyncClient`. Lint: `ruff check`, `ruff format --check`, `mypy app`.
- Audit: `pip-audit`.

### Medium: Bun + TypeScript
- Bun, TypeScript strict, Hono, Drizzle ORM + drizzle-kit migrations, Zod (`@hono/zod-validator`),
  `Bun.password` (argon2id), `hono/secure-headers`, `hono/cors`, a rate limiter
  (`hono-rate-limiter`).
- Layout: `backend/src/{index.ts, env.ts, db/{schema.ts,client.ts}, middleware/, routes/, services/, lib/}`,
  `backend/test/`, `backend/drizzle/`.
- Tests: `bun test`. Lint: `bunx tsc --noEmit`, `bunx biome check`.
- Audit: `bun audit` (or `npm audit --omit=dev` on a lockfile).

### Large: Go
- Go 1.23+, `net/http` + `chi`, `pgx/v5`, `sqlc` (typed queries), `goose` migrations,
  `golang.org/x/crypto/argon2`, `go-playground/validator`, `httprate`.
- Layout: `backend/cmd/api/main.go`, `backend/internal/{config,db,auth,http/{handlers,middleware},service,store}`,
  `backend/migrations/`, `backend/queries/`.
- Tests: `go test ./...` (+ `-race`). Lint: `go vet ./...`, `staticcheck ./...`.
- Audit: `govulncheck ./...`.

### Database
- **PostgreSQL 16+** for everything (docker-compose for dev). Enable **Row-Level Security** on every
  table that holds user- or tenant-owned rows, as defense in depth. The app also scopes every query
  itself; RLS is the second lock. Set the current user/tenant per transaction
  (`SET LOCAL app.user_id = …`).
- The one exception is a single-user local tool with no accounts, which can use SQLite.
- Primary keys: UUIDv7 (or random UUIDs). They aren't an access control, but they stop enumeration.

### Auth (all backends)
- Server-side sessions: an opaque random token (≥ 256 bits), stored hashed in a `sessions` table,
  sent as an `HttpOnly; Secure; SameSite=Lax` cookie, with sliding expiry and rotation on login.
  Prefer this to JWTs for a web app with its own backend.
- Passwords: argon2id. Email verification and password reset use single-use, hashed, expiring
  tokens.
- OAuth (Google etc.) when chosen: authorization code + PKCE + state; link accounts by verified
  email only.
- CSRF: SameSite=Lax cookie plus an Origin/`Sec-Fetch-Site` check on state-changing requests.

### Frontend
- **SvelteKit:** Svelte 5 (runes), TypeScript, `adapter-node`, prerender the public marketing
  pages, `+page.server.ts` loads for data, form actions for mutations.
- **Next.js:** App Router, TypeScript, Server Components by default, `'use client'` only on
  interactive leaves, the Metadata API, `app/sitemap.ts`, `app/robots.ts`.
- Both:
  - Tailwind CSS v4 with CSS variables from the design tokens (`frontend-quality.md`).
  - A typed API client generated from `mnm/contracts/openapi.yaml` (`openapi-typescript` +
    `openapi-fetch`).
  - Zod on forms.
  - Playwright for e2e.
- **Same-origin API:**
  - In dev, the frontend proxies `/api/*` to the backend (Vite `server.proxy` or Next.js
    `rewrites`).
  - In prod, a reverse proxy does the same.
  - Cookies stay first-party, and CORS stays a strict allowlist.

## 4. Repo layout (new project)

```
backend/            # one of the stacks above
frontend/           # SvelteKit or Next.js
e2e/                # Playwright (owned by qa)
docker-compose.yml  # postgres (+ mailpit for emails in dev)
.env.example        # every variable, no real secrets
README.md           # setup, run, test, deploy
```

Every package exposes the same script names so prompts and QA can be generic: `dev`, `test`,
`lint`, `build`, `check` (= lint + typecheck + test). For Python use a `Makefile` or `justfile`
with the same targets. On Windows they must also work as `uv run …` / `bun run …`.

## 5. Existing project

Keep the existing stack, versions, libraries and conventions. Never migrate or add a parallel
framework. Use the rules above only for what the repo lacks, e.g. pick the test runner when there
are no tests.
