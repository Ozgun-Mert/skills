# Writing the worker brief (Phase 5)

One headless worker writes all the tests: `claude -p "/goal <condition>"`, with
`references/worker-contract.md` appended to its system prompt. It sees only the condition, the
contract and what it reads, so `qa/goal-prompt.md` must be complete on its own and cheap to start.

## How /goal judges (design the condition around this)

- After every turn, a small model reads the conversation and decides: not met / met / impossible.
- It **can't** run commands or read files. A criterion counts only when its proof (command output,
  exit code, printed file) appears in the worker's transcript.
- The condition may be at most 4,000 characters; keep it near 1,500. Details live in the brief.
- Always end with a turn cap so a stuck worker stops.

## Condition template

Fill `<TEST_COMMAND>`, `<SKILL_DIR>` (real absolute path, forward slashes) and `<N>`:

```text
Write the QA test suite described in qa/goal-prompt.md (read it first; it is your full brief).
The goal is met only when this session's transcript shows ALL of:
1. `<TEST_COMMAND>` run to completion with its output printed. Failing assertions are allowed (they are findings for the report); every test file must load and run.
2. `python "<SKILL_DIR>/scripts/run_tests.py" --root .` printing a SUMMARY line with harness_errors=0.
3. `python "<SKILL_DIR>/scripts/check_tests.py" --root .` printing READY.
4. qa/worker-report.md written in the format the brief gives, then printed with `cat`.
Expected results come only from qa/TEST_DECISIONS.md: never change an expectation to match what the code does, never skip or weaken a test to get green, never edit application source. Or stop after <N> turns with qa/worker-report.md listing what is unfinished.
```

Turn cap `N`: `40 + active decisions ÷ 2`, at most 200. A rerun with a short work list: 40.

## Brief sections (all required, in this order; `launch_worker.py --check` verifies)

1. `## Goal condition` — the fenced `text` block above.
2. `## Context pack` — exactly what to read, nothing else:
   - `qa/TEST_DECISIONS.md` (all of it: setup, global rules, access matrix, decisions)
   - `qa/env.json` (stack, runner, DB, externals)
   - `qa/function-map.json` entries for the functions in the work list (or "all kept functions")
   - the function line ranges to read (`src/orders/service.ts:40-88`), the route registration
     file(s), the auth middleware, the app/server entry (to build the app in tests), the ORM schema
     / migrations folder, 1–2 existing test files as style examples if any
   - `SKILL_DIR/references/test-setup.md` and `SKILL_DIR/references/attack-matrix.md`
3. `## Layout and naming` — test folder, helper folder, file naming, the describe/title rule
   (see the contract), the manifest scripts to add, `qa/test-commands.json`.
4. `## Setup` — copied from the Setup section of TEST_DECISIONS.md, made concrete: which DB
   strategy, which engine and migration command, which services are sandboxed vs mocked, the
   production guard, the clock strategy.
5. `## Work list` — functions grouped by module, each with its decision IDs, the attack-matrix
   rows that apply (by route), and `tested_via` notes. First run: everything active. Rerun: only
   new/changed decision IDs, plus **retired IDs whose tests must be removed** (only from files the
   skill created under the qa test folder).
6. `## Constraints` — the hard rules: allowed files (test folder, helpers, test config, manifest
   scripts/dev deps, `.env.test.example`, `qa/`), forbidden files (everything else, especially app
   source and existing tests), no git changes, no live keys, no production DB.
7. `## Report` — the format of `qa/worker-report.md`:

```markdown
# Worker report: done | partial
## Commands
- full suite: `bun run test`  ·  junit/coverage/file commands written to qa/test-commands.json
## Files added / changed
- tests/qa/… (N files) · tests/qa/_support/… · package.json (scripts.test, devDependencies: …)
## Dependencies added (dev only)
## Decisions covered
- N of M active decision IDs have at least one test; untestable: see qa/untestable.json
## Suite result
- SUMMARY line from run_tests.py
## Harness notes
- DB strategy used, mocks, anything non-deterministic
## Unfinished / risks
```

## Validate before launching

`python "SKILL_DIR/scripts/launch_worker.py" --root . --check` prints the condition length, the
sections found, decision IDs in the work list that don't exist in TEST_DECISIONS.md, and the turn
cap. Fix every error, then launch.
