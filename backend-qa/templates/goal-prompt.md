---
run: first | rerun
max_turns: <N>
skill_dir: <SKILL_DIR>
---

# QA test writer brief

## Goal condition

```text
Write the QA test suite described in qa/goal-prompt.md (read it first; it is your full brief).
The goal is met only when this session's transcript shows ALL of:
1. `<TEST_COMMAND>` run to completion with its output printed. Failing assertions are allowed (they are findings for the report); every test file must load and run.
2. `python "<SKILL_DIR>/scripts/run_tests.py" --root .` printing a SUMMARY line with harness_errors=0.
3. `python "<SKILL_DIR>/scripts/check_tests.py" --root .` printing READY.
4. qa/worker-report.md written in the format the brief gives, then printed with `cat`.
Expected results come only from qa/TEST_DECISIONS.md: never change an expectation to match what the code does, never skip or weaken a test to get green, never edit application source. Or stop after <N> turns with qa/worker-report.md listing what is unfinished.
```

## Context pack

Read these, and only these:
- `qa/TEST_DECISIONS.md` (all)
- `qa/env.json`
- `qa/function-map.json` — entries: <F-ids or "all with status other than skipped">
- Code to learn how to call things (not what to expect):
  - app entry / factory: `<src/app.ts:1-80>`
  - route registration: `<src/routes/index.ts>`
  - auth middleware: `<src/middleware/auth.ts:1-60>`
  - DB schema / migrations: `<prisma/schema.prisma>` · `<migrations/>` (names only)
  - function ranges: `<src/orders/service.ts:40-88>`, …
- Style examples (existing tests): `<tests/orders.test.ts:1-60>` (or "none")
- `<SKILL_DIR>/references/test-setup.md`, `<SKILL_DIR>/references/attack-matrix.md`

## Layout and naming

- New tests: `<tests/qa/>`, one file per module or per route group (`orders.create.test.ts`).
- Helpers: `<tests/qa/_support/>` — app factory, user/token factory, DB reset, clock, mocks.
- One describe per function: `F012 orders.createOrder`; every test title starts with its IDs:
  `[F012-D3] …`, `[S-1][G-2] …`.
- Manifest: `<package.json scripts.test = "bun test">` (keep any existing scripts).
- Write `qa/test-commands.json` (test, junit, coverage, file commands).

## Setup

<Concrete version of the Setup table: DB strategy and engine, migration command, env file used
for tests, production guard, sandboxed vs mocked services and the mocking library, clock.>

## Work list

### <module> (risk: high)
- F003 auth.login · POST /auth/login — decisions F003-D1…D5; attack rows: input §1, access §2
  (anonymous only), abuse §4 (lockout, XFF spoof); OBV-1, OBV-2
- F004 … (tested via F003: no separate unit test)

### Global / matrix
- G-1…G-5, OBV-1…OBV-3: covered across routes (at least one test each)
- S-1…S-n: for every route touching the resource, per attack-matrix §2
- SEC-1…SEC-n

### Retired (rerun only)
- Remove tests for: <F009-D2> (only in files under the qa test folder)

## Constraints

- Allowed to create/modify: `<tests/qa/**>`, test config (`<bunfig.toml>`), `package.json`
  scripts + devDependencies, the lockfile, `.env.test.example` (placeholders), `qa/**`.
- Never modify: application source, existing tests, migrations, `.env*` with real values, CI
  files. No git commands that change state. No live keys. Never point tests at DATABASE_URL.
- Every active decision ID gets at least one test, or an entry with a real reason in
  `qa/untestable.json`.

## Report

Write `qa/worker-report.md`:

```markdown
# Worker report: done | partial
## Commands
## Files added / changed
## Dependencies added (dev only)
## Decisions covered
## Suite result
## Harness notes
## Unfinished / risks
```
