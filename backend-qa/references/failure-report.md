# Run, blame-check and report (Phase 6)

The report must only blame the code for real code bugs. A test the worker got wrong, a flaky
timing issue or a broken test DB must never show up as "your code is broken".

## 1. Run the full suite

```
python "SKILL_DIR/scripts/run_tests.py" --root . --coverage
```

- Runs `junit_command` (and `coverage_command` with `--coverage`) from `qa/test-commands.json`,
  with `CI=true`, a time cap, and masked output.
- Writes `qa/results/results.json`: every test (`key`, `name`, `suite`, `file`, `status`
  passed/failed/error/skipped, `message`, `function`, `decisions`, `harness`), per-function totals,
  coverage per function when available, and prints:
  `SUMMARY total=… passed=… failed=… errors=… skipped=… harness_errors=… functions_failing=…`
  followed by the failing test keys.
- `--report` mode starts here.

## 2. Blame check (every failed or errored test)

Work through the failures in this order and decide one category per test:

1. **flaky** — rerun the test file twice:
   `python "SKILL_DIR/scripts/run_tests.py" --root . --file <test file> --times 2`.
   If the test passes in either rerun, it's flaky. Report it with what varies (timing, order,
   shared data) and how to make it deterministic.
2. **environment** — `harness: true` in results, or the message is about the setup, not the
   behavior (connection refused, missing env var, migration failed, container didn't start,
   module/helper not found in the test folder). If the test harness is at fault, it goes to the
   worker (step 4). If the user's machine is (Docker not running, no network), report it with the
   steps to fix the environment.
3. **test bug** — read the test (only its lines) and the decision(s) it cites. It's a test bug when
   the test asserts something the decision does not say: a guessed error code string, a response
   field name the API never promised, the wrong route/payload shape, a missing auth header in a
   test that isn't about auth, data from another test, an expectation contradicting a `G-n` rule.
4. **Fix round** — collect all test bugs and harness faults into **one** message and resume the
   worker:
   `python "SKILL_DIR/scripts/launch_worker.py" --root . --resume --message "<list: test key, what is wrong, which decision it must follow>"`.
   Then rerun step 1. At most **2** fix rounds. Corrected tests are listed in the report under
   "Tests corrected during the run"; anything still wrong after 2 rounds is reported as a test bug
   with the reason.
5. **code bug** — the test matches its decision and the app behaves differently. Read the
   function's line range (`qa/function-map.json`), find the line where the behavior diverges (the
   missing check, the wrong comparison, the unscoped query, the trusted client field), and work out
   why. If the cause is in a shared piece (middleware, ORM base, error handler), point there and
   say which other functions it affects.

Existing (pre-skill) tests have no decision IDs: their expectation is the test itself. A failing
existing test is reported as a code bug or test bug the same way, but never "corrected" by you or
the worker — if you think the existing test is wrong, say so in the report and leave it.

Keep your context small: read only failing tests and the function ranges they point to.

## 3. `qa/results/analysis.json`

```json
{
  "failures": [
    {
      "test": "<key from results.json>",
      "category": "code_bug | flaky | environment | test_bug",
      "decisions": ["F012-D3"],
      "title": "Order quantity 0 is accepted",
      "expected": "400 validation error, no order written (F012-D3)",
      "actual": "201 Created, order with quantity 0 saved",
      "why": "createOrder validates quantity with `> 100` only; nothing rejects values below 1.",
      "where": [
        {"file": "src/orders/service.ts", "line": 52, "note": "the only quantity check"},
        {"file": "src/orders/schema.ts", "line": 8, "note": "schema allows 0"}
      ],
      "fix": [
        "Decide where input validation lives for orders (the schema is the natural place).",
        "Add a lower bound of 1 to the quantity rule in the order schema.",
        "Make sure the route validates the body with that schema before calling the service.",
        "Re-run `bun run test` and check F012-D3 and the other F012 tests pass."
      ],
      "severity": "high | medium | low"
    }
  ],
  "test_fixes": [
    {"test": "<key>", "what": "asserted error code `QTY_INVALID`; decision only says 400"}
  ],
  "notes": ["optional one-liners for the summary"]
}
```

Rules for `fix`: **the process, not code.** Plain steps a developer follows: what to decide, where
to change, what rule to add or move, what to check afterwards. No code snippets, no diffs, no
pseudo-code. 2–6 steps. Name files and functions, not line edits.

`severity`: high = security/access/money/data loss; medium = wrong result or status a client
relies on; low = cosmetic error shape, message text.

## 4. Render the report

```
python "SKILL_DIR/scripts/make_report.py" --root .
```

It refuses (exit 1) while any failed/errored test lacks an analysis entry, and lists them.
Output `qa/TEST_FAILED.md`:

1. **Summary** — command, date, totals, code bugs by severity.
2. **Functions** — one row per function: ✅ all passed / ❌ N failed / ⚠️ flaky or environment,
   with tests passed/failed and a VS Code link to the function.
3. **Code bugs** — grouped by function, highest severity first. Each: title, test name,
   decisions, expected vs actual, why, *Where* links (`[src/orders/service.ts:52](vscode://file/C:/…/src/orders/service.ts:52:1)`),
   test link, *How to fix* steps.
4. **Flaky**, **Environment**, **Test bugs left** — same format, shorter.
5. **Tests corrected during the run**.
6. **Coverage gaps** — functions with no tests, and kept functions under 60% line coverage
   (when coverage ran). Suggest the decision to ask next time, not code.

The `vscode://file/<absolute path>:<line>:<column>` links open the exact line in VS Code when
clicked from the markdown preview, a browser or most terminals.
