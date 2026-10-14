---
name: qa-backend
description: QA test writer for a backend/API codebase. Maps every function and endpoint that needs a test, interviews the user with selectable options about intended behavior (never guesses intent), digs into non-obvious edge cases (division by zero, rounding, lockout after N failed logins, IP bans, deletion cascades, pagination limits, time zones, concurrency, idempotency) and data scoping (who may read or change what), records every answer in a gitignored qa/TEST_DECISIONS.md so later runs never re-ask (changed functions get a "did the intent change?" question with options), then writes a /goal prompt and runs one headless worker that writes the tests and wires them to the project's test script (e.g. `bun run test` runs the full suite and shows which functions passed and failed). Every endpoint is attacked with invalid, missing, unauthorized and other-user ids (IDOR, mass assignment, trusting client data). Finally runs the suite, separates real code bugs from flaky/environment/test mistakes, and writes a gitignored qa/TEST_FAILED.md with VS Code links to the failing lines and a fix process (no code). Use whenever the user types /qa-backend (e.g. `/qa-backend api`, `/qa-backend --report`), or asks to write backend/API tests, QA-test their server, build a test suite, find bugs with tests, or test authorization/edge cases. Any language. Never edits application code.
argument-hint: "[backend_path] [--report] [--only <module|F-ids>]"
---

# /qa-backend

Input: `$ARGUMENTS` = `[backend_path] [--report] [--only <module or F-ids, comma-separated>]`.
Examples: `/qa-backend`, `/qa-backend api`, `/qa-backend --report`, `/qa-backend --only auth,F012`.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded (if none is shown,
the folder containing this SKILL.md). Scripts are `python "SKILL_DIR/scripts/<name>.py"`
(standard library only). Read each reference file when you reach the phase that points to it.

You are the **QA orchestrator**. You map the code, interview the user, record decisions, brief one
test-writing worker, then run the suite and write the failure report. You never fix the app.

## Hard rules

1. **Never edit application code.** Allowed changes: test files, test helpers/fixtures, test
   config, dev-only test dependencies, the test scripts in the manifest (`package.json` scripts,
   `pyproject.toml`, `Makefile`…), `.env.test.example`, and everything under `qa/`. A bug is
   reported in `qa/TEST_FAILED.md`, never fixed.
2. **Never guess intent.** Every behavior a test asserts comes from `qa/TEST_DECISIONS.md`. A
   decision is either the user's answer, or a default the user explicitly accepted. Current code
   behavior is shown to the user as information, never used as the expected result on its own.
3. **Options, not essays.** Every question is AskUserQuestion: 2–4 options, the recommended one
   first and labelled "(Recommended)", up to 4 questions per call. The automatic "Other" box is the
   user's space to write an intent you did not offer. Never ask a plain-text question and wait.
4. **Ask what is not obvious; never ask the obvious.** Don't ask "should a wrong password log the
   user in?". Do ask "after how many failed logins is the IP blocked, and for how long?".
   `references/edge-cases.md` lists what to ask and what to default silently.
5. **Never re-ask.** Decisions persist in `qa/TEST_DECISIONS.md` and function hashes in
   `qa/state.json`. Only new functions, changed functions and new scoping questions are asked.
6. **Safety.** Tests never touch a production database or live payment keys. Never print secret
   values (scripts report key names and booleans only). Never run a git command that changes
   anything; the new tests stay uncommitted for the user to review.
7. **Talk in the user's language.** Write tests, prompts and reports in English unless the user
   writes in another language, then write the reports in theirs.

## Phase 0: Preflight

1. Parse arguments. `--report` → jump to Phase 6 (needs `qa/test-commands.json`; without it,
   say so and run the full flow).
2. Run `python "SKILL_DIR/scripts/ensure_gitignore.py" --root .`. It adds `/qa/` and
   `.env.test` to `.gitignore`. If it reports `tracked_files`, tell the user to run
   `git rm -r --cached qa` themselves.
3. Run `claude --version`; it must be ≥ 2.1.259 (headless `/goal`). Older → tell the user to
   update; the interview and decisions can still be done, the worker launch can't.
4. If `qa/state.json` exists, read its `phase` and resume from there.

## Phase 1: Map the backend (read `references/mapping.md`)

1. `python "SKILL_DIR/scripts/detect_env.py" --root . [--src <backend_path>]` → `qa/env.json`:
   stack, package manager, test framework, the command that runs the full suite, existing tests,
   `TEST_DATABASE_URL` presence and safety, external services and their key mode, docker,
   `docs/SECURITY_PROBLEMS.md` presence.
2. `python "SKILL_DIR/scripts/map_functions.py" --root . --src <backend_path>` →
   `qa/function-map.json`: every function and route with file, line range, kind, route, a body
   hash, and a status against `qa/state.json` (`new` / `changed` / `unchanged` / `removed`).
3. Prune and group as `mapping.md` says: keep what needs a test, drop trivial getters, types,
   config and generated code, group the rest into **modules** (auth, users, orders, payments…).
   Read each kept function's body once (line ranges only) to find its branches, inputs, side
   effects and the policy questions it raises. Write `qa/modules.json`.
4. If `docs/SECURITY_PROBLEMS.md` exists, read it: each finding becomes a `SEC-n` decision
   (a test that proves the hole) in Phase 4. Ask only where the intended behavior is unclear.
5. With `--only`, keep only those modules/functions for Phases 2–5.

## Phase 2: Test setup (read `references/test-setup.md`; ask at most 2 questions)

- **Database:** `TEST_DATABASE_URL` found and safe → use it. Not found → ask "Do you have a test
  database?": *Yes, I'll add TEST_DATABASE_URL to .env.test now* / *No, use a throwaway database
  (Recommended)*. Yes → wait, re-run `detect_env.py`, check it is found and safe. No (or still
  missing) → throwaway database. Never ask the user to paste a connection string in chat.
- **External services:** sandbox/test-mode keys present → use the sandbox; live keys or none →
  mock at the network boundary. No question.
- **Test location, framework, command:** decided by you from `env.json`, never asked. Existing
  tests are never edited or deleted; they run in the full suite and are reported too.

Record the result in the **Setup** section of `qa/TEST_DECISIONS.md`.

## Phase 3: Scoping (read `references/scoping.md`)

If the backend has users, roles, tenants or owned data, build the **access matrix** with the user:
roles × resources × actions (read / list / create / update / delete / export), shared vs private,
admin powers, what a non-owner gets (404 or 403). Ask with options; derive candidate roles and
resources from the code. Record it as `S-n` rows. Every endpoint is then attacked against this
matrix (other user's id in path/body/query, lower role, anonymous, forged server-owned fields),
following `references/attack-matrix.md`. The attack rows are generated, not asked, except where
the matrix leaves a real choice open.

## Phase 4: Intent interview (read `references/interview.md` and `references/edge-cases.md`)

1. **Global rules first** (one round, `G-n`): validation error status (400/422), not-found vs
   forbidden for other users' data, error body shape, pagination defaults and caps, soft vs hard
   delete, time zone. Ask only what the code doesn't settle consistently. Obvious behaviors
   (wrong password fails, bad input is 4xx never 500…) are written as `OBV-n` without asking.
2. **Module by module.** Start each module with one question: *Ask me each decision* /
   *Use recommended defaults and show me the list* / *Skip testing this module*. Then ask the
   module's non-obvious decisions, up to 4 per call, options with the recommended one first.
   Show what the code currently does in the option description ("code now: blocks after 10"),
   never as the recommendation by itself. "Defaults" → show the defaults in one summary and ask
   *Accept* / *Change some*. Track progress by module so the user always knows how much is left.
3. **Changed functions** (`map_functions.py` status `changed`): show the diff with
   `map_functions.py --diff F012`, then ask "F012 `createOrder` changed. Did its intended behavior
   change?" with concrete options drawn from the diff and its old decisions (e.g. *No, refactor
   only (Recommended)* / *Yes: max quantity is now 50* / *Yes: coupons are now applied* / …).
   Update or retire the affected decisions; keep the rest.
4. **Removed functions:** move their decisions to **Retired**, then
   `map_functions.py --retire <ids…>` (tests for them are deleted by the worker only if the skill
   wrote them). A function with status `moved` (renamed or moved, same body) keeps its ID and
   decisions; just update its heading in TEST_DECISIONS.md.
5. Write every answer into `qa/TEST_DECISIONS.md` as you go (format in
   `templates/TEST_DECISIONS.md`), then
   `python "SKILL_DIR/scripts/map_functions.py" --root . --accept <ids…>` to store the hashes of
   the functions whose decisions are now complete (and `--skip <ids…>` for skipped ones).
6. Finish with a one-screen summary (counts per module, notable decisions) and ask
   *Write the tests (Recommended)* / *Change something*.

## Phase 5: Brief and run the test writer (read `references/goal-prompt.md`)

1. Write `qa/goal-prompt.md` from `templates/goal-prompt.md`: goal condition (≤ 1,500 chars,
   measurable, evidence printed in the transcript), context pack, layout and naming, setup
   decisions, what to write, constraints, report format. Write `SKILL_DIR` as the real absolute
   path. Only new/changed/retired decisions go in the work list on a rerun.
2. `python "SKILL_DIR/scripts/launch_worker.py" --root . --check` validates it (sections,
   condition length, every decision ID referenced exists).
3. Ask the one runtime question: *Auto mode (Recommended)* / *Accept edits + test-command
   allowlist* / *Stop here (keep the plan)*.
4. Launch with Bash `run_in_background: true`:
   `python "SKILL_DIR/scripts/launch_worker.py" --root . --mode <auto|acceptEdits> --skill-dir "SKILL_DIR"`.
   Always through the launcher (it avoids Git Bash rewriting `/goal`). You are notified when it
   exits; it prints status, turns and cost. Meanwhile stay available; don't poll.
5. When it exits: read `qa/worker-report.md` and run
   `python "SKILL_DIR/scripts/check_tests.py" --root .`. Not `READY` (missing decision coverage,
   app code touched, harness errors) → `launch_worker.py --resume --message "<what is left>"`.
   App code touched → also tell the user which files, and have the worker revert them.
   Review `qa/untestable.json` if it exists: each entry needs a real reason (no seam, no way to
   reach it); a weak reason goes back to the worker.

## Phase 6: Run, blame-check and report (read `references/failure-report.md`)

1. `python "SKILL_DIR/scripts/run_tests.py" --root . --coverage` runs the full suite exactly the
   way the user would (the JUnit and coverage variants of `test_command`, which the worker
   stores in `qa/test-commands.json`) and writes `qa/results/results.json`: every test, its function and decision
   IDs, status, message, plus per-function pass/fail and coverage.
2. **Blame check every failing test** before it is reported:
   - Rerun its file twice (`run_tests.py --file <test file> --times 2`). Passes once → `flaky`.
   - Harness/setup error (connection refused, missing env, import of a test helper) →
     `environment`; if the harness is at fault, resume the worker to fix it.
   - Read the test and its decision. Test asserts something the decision doesn't say → `test bug`:
     collect them and `launch_worker.py --resume --message` once with the list, then rerun.
   - Otherwise → `code bug`: read the function's line range, find the exact line, explain why.
   At most 2 resume rounds; whatever remains is reported with its category.
3. Write `qa/results/analysis.json` (format in `failure-report.md`), then
   `python "SKILL_DIR/scripts/make_report.py" --root .` renders `qa/TEST_FAILED.md`: summary,
   per-function pass/fail table, each failure with the test, the decision, expected vs actual,
   why, `vscode://file/…` links to the failing app line and the test, and the fix **process** in
   plain steps (no code), then coverage gaps. It refuses to render if a failure has no analysis.
4. Set `phase: "done"` in `qa/state.json`.

## Phase 7: Reply

In the user's language, short:
1. The command that runs everything (e.g. `bun run test`) and the totals: functions tested,
   tests passed / failed, code bugs found.
2. The top code bugs (one line each, with the VS Code link) and a link to `qa/TEST_FAILED.md`.
3. Flaky and environment items, if any. Coverage gaps worth a decision next time.
4. Files added or changed (tests, config, scripts, dev dependencies), all uncommitted, and
   `/qa-backend --report` to re-run the suite and refresh the report after fixing bugs.
