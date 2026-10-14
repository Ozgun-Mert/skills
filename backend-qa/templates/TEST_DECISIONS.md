# Test decisions

<!--
Written by /qa-backend. Gitignored. The single source of truth for what the tests expect.
IDs are permanent: never renumber, never reuse. Sources: user (picked in the interview),
default (recommended option the user accepted in a defaults summary), obvious (never asked; only
one sane answer), security (from docs/SECURITY_PROBLEMS.md).
Decision rows must keep the table format `| ID | ... |`; scripts parse the ID column.
-->

Last updated: YYYY-MM-DD · backend: `api/` · functions decided: N · active decisions: N

## Setup

| Item | Decision |
|---|---|
| Full-suite command | `bun run test` |
| Runner | bun test (existing) |
| New tests folder | `tests/qa/` (helpers in `tests/qa/_support/`) |
| Database | TEST_DATABASE_URL from `.env.test` · or · throwaway Postgres 16 via Testcontainers, migrations: `bunx prisma migrate deploy` |
| Production guard | refuse when the DB URL equals DATABASE_URL or the host isn't local and the name lacks "test" |
| External services | Stripe: sandbox (test keys present) · Resend: mocked (in-memory outbox) · S3: mocked |
| Clock | fake timers for lockout/expiry tests |
| Existing tests | kept, run in the full suite, never edited |

## Global rules

| ID | Situation | Expected | Source |
|---|---|---|---|
| G-1 | Request body fails validation | 400 `{ "error": { "code", "message" } }`, nothing written | user |
| G-2 | Authenticated user requests someone else's private resource | 404 (same as not found) | user |
| G-3 | No/invalid/expired auth | 401 | obvious |
| G-4 | Unknown/extra body fields | ignored, never applied | user |
| G-5 | List endpoints | default 20, max 100, `limit` above max is clamped | default |

## Obvious checks

| ID | Situation | Expected | Source |
|---|---|---|---|
| OBV-1 | Any malformed or wrongly typed input | 4xx, never 500, no stack trace | obvious |
| OBV-2 | Any response | never contains password hashes, tokens, secrets | obvious |
| OBV-3 | Client sends server-owned fields (`id`, `role`, `owner_id`, totals) | not applied | obvious |

## Access matrix

| ID | Resource | Action | Allowed | Denied → response | Source |
|---|---|---|---|---|---|
| S-1 | order | read | owner, admin | others → G-2, anonymous → G-3 | user |
| S-2 | order | list | own orders only; admin sees all | filtered, never an error | user |

## Security findings

| ID | Situation | Expected | Source |
|---|---|---|---|
| SEC-1 | `PATCH /users/:id` with another user's id (SECURITY_PROBLEMS.md #3) | 404, target unchanged | security |

## Modules

| Module | Risk | Functions | Mode | Status |
|---|---|---|---|---|
| auth | high | F001, F002, F007 | asked | decided |
| reports | low | F020 | — | skipped: read-only export, out of scope |

---

## F003 · auth.login · POST /auth/login

- file: `src/auth/login.ts:12-64` · module: auth · hash: `3fa9c1d2e4b0` · status: decided

| ID | Situation | Expected | Source |
|---|---|---|---|
| F003-D1 | 5 failed logins for one account within 15 min | 6th attempt → 429 `account_locked`, even with the correct password | user |
| F003-D2 | Lock window passes (15 min, fake clock) | correct password logs in; counter reset | user |
| F003-D3 | 20 failed logins from one IP across accounts within 15 min | IP blocked for 1 h → 429 | user |
| F003-D4 | `X-Forwarded-For` rotated during the attack | still blocked (proxy not trusted) | user |
| F003-D5 | Unknown email vs wrong password | identical status and body | default |

Notes: user said "lock email only on the first lock, not every attempt" (F003-D1).

---

## Retired

| ID | Was | Retired on | Why |
|---|---|---|---|
| F009-D2 | max quantity 100 | YYYY-MM-DD | user: max is now 50 (replaced by F009-D6) |
