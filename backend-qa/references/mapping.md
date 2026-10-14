# Mapping the backend (Phase 1)

Goal: a list of the functions that deserve a test, grouped into modules, with enough understanding
of each to ask good questions. One pass, line ranges only, no re-reading.

## 1. Run the scripts

```
python "SKILL_DIR/scripts/detect_env.py"   --root . [--src <backend_path>]
python "SKILL_DIR/scripts/map_functions.py" --root . [--src <backend_path>]
```

- `detect_env.py` prints a short summary and writes `qa/env.json`.
- `map_functions.py` prints counts per status and per kind and writes `qa/function-map.json`.
  Each entry: `id` (stable `F001…`), `key` (`file::name#n`), `name`, `file`, `start`, `end`,
  `lines`, `kind`, `exported`, `trivial`, `route` (`{method, path}` or null), `hash`, `status`.
- No `--src`: the script picks the backend folder (`api/`, `server/`, `backend/`, `src/`, `app/`,
  else the root) and skips frontend folders it recognizes. If the repo is a monorepo and the
  pick is wrong, rerun with `--src`.

## 2. Keep or drop

**Keep** (needs a test):
- every route handler (`kind: route`) and every middleware/guard (`kind: middleware`)
- services / use cases / domain logic with a branch, a calculation, a DB write or an external call
- validators, parsers, money/time/permission helpers, anything security-relevant (hashing, tokens,
  signature checks, webhook verification)
- background jobs, queue consumers, cron handlers, webhook handlers

**Drop** (status `skipped`, reason recorded, never asked):
- `trivial: true` functions with no branch (plain getters/setters, pass-through wrappers)
- type/interface/DTO declarations, constants, config loaders, DI wiring, `main()` bootstrap
- migrations, seeds, generated clients (Prisma, OpenAPI, protobuf), vendored code
- functions only used by tests or scripts

When in doubt, keep it: a function that is cheap to test is cheap to keep.

A function tested through its route doesn't need a second, separate unit test unless it has
branches the route can't reach (e.g. a rounding helper with many inputs). Note this as
`tested_via: F0xx` in `qa/modules.json` so the worker writes one test, not two.

## 3. Group into modules

Group by domain, not by folder: `auth`, `users`, `orders`, `payments`, `admin`, `files`,
`notifications`, `webhooks`, `jobs`, `utils`. A module is what one interview round covers (5–25
decisions). Split big ones (`orders-create`, `orders-manage`).

Write `qa/modules.json`:

```json
{"modules": [
  {"name": "auth", "risk": "high", "functions": ["F001", "F002", "F007"],
   "notes": "login, register, reset, refresh; rate limiter in middleware F007"}
],
 "skipped": [{"id": "F030", "reason": "trivial getter"}],
 "tested_via": {"F014": "F003"}}
```

`risk`: `high` for auth, money, permissions, deletion, personal data, uploads, webhooks; `medium`
for normal CRUD; `low` for read-only helpers. High-risk modules are interviewed first and always
default to *Ask me each decision*.

## 4. Read each kept function once

Read only `file:start-end` from the map (plus the route registration line and the middleware it
uses). For each function note, in your head or in `qa/modules.json` `notes`:

- inputs (path/query/body params, types, which are optional)
- branches and what each returns or throws
- side effects (DB writes, emails, payments, files, cache)
- what it trusts from the client (ids, prices, roles, owner fields)
- the **policy questions** it raises (see `edge-cases.md`): limits, thresholds, rounding,
  what happens on zero/empty/duplicate/concurrent/deleted, who may call it

Don't read whole files, lockfiles, `node_modules`, build output or the frontend. Don't re-read a
function you already read; the notes are enough to write questions.

## 5. Security report (optional input)

If `docs/SECURITY_PROBLEMS.md` exists (from `/check-backend-security`), read its findings list.
Each finding with a reachable endpoint or function becomes a `SEC-n` decision: "this request must
be rejected / scoped / not leak X". The test proves the hole while it exists and guards against
regressions after the fix. Skip findings that aren't testable (dependency versions, headers set
by the CDN) and note them as such.
