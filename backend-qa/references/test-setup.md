# Test setup (Phase 2, and the worker's setup rules)

Everything here is decided by you from `qa/env.json`; only the database question is ever asked.
Record the result in the **Setup** section of `qa/TEST_DECISIONS.md` so the worker follows it.

## 1. The full-suite command

The user must be able to run **one command** that runs every test (existing + new) and shows, per
function, which tests passed and failed. Use the project's own package manager and runner.
If the project already has a test runner, keep it. If not, pick the ecosystem default below.

| Ecosystem | Runner (default when none) | Full-suite command the user runs | Manifest entry |
|---|---|---|---|
| Bun | `bun test` | `bun run test` | `package.json` `scripts.test` |
| Node + npm/pnpm/yarn | Vitest (ESM/TS) or the existing Jest / `node --test` | `npm test` / `pnpm test` / `yarn test` | `package.json` `scripts.test` |
| Deno | `deno test` | `deno task test` | `deno.json` `tasks.test` |
| Python (uv / poetry / pip) | pytest | `uv run pytest` / `poetry run pytest` / `pytest` | `pyproject.toml` `[tool.pytest.ini_options]` + optional `Makefile test` |
| Go | `go test` (+ `gotestsum` for JUnit) | `go test ./...` or `make test` | `Makefile` |
| Java / Kotlin | JUnit 5 (Maven Surefire / Gradle) | `mvn test` / `./gradlew test` | build file |
| C# | xUnit / NUnit / MSTest | `dotnet test` | test project |
| PHP | PHPUnit / Pest | `composer test` | `composer.json` `scripts.test` |
| Ruby | RSpec / Minitest | `bundle exec rspec` / `rake test` | `Rakefile` / `.rspec` |
| Rust | `cargo test` (+ `cargo nextest` for JUnit) | `cargo test` | — |

If a `test` script exists but runs only part of the suite (one folder, unit only), extend it so it
runs everything; keep the old behavior available under a new name (`test:unit`). Never remove a
script the user had.

## 2. Machine-readable variants (`qa/test-commands.json`)

The worker writes `qa/test-commands.json`; `run_tests.py` reads it:

```json
{
  "test_command": "bun run test",
  "junit_command": "bun test --reporter=junit --reporter-outfile=qa/results/junit.xml",
  "junit_paths": ["qa/results/junit.xml"],
  "coverage_command": "bun test --coverage --coverage-reporter=lcov --coverage-dir=qa/results/coverage",
  "coverage_paths": ["qa/results/coverage/lcov.info"],
  "file_command": "bun test {file}",
  "cwd": "."
}
```

`junit_command` must run the **same** set of tests as `test_command`. `{file}` in `file_command`
is replaced by one test file path. All commands run from `cwd` (relative to the project root).

| Runner | JUnit | Coverage (lcov / Cobertura / JaCoCo / Go profile) |
|---|---|---|
| bun test | `--reporter=junit --reporter-outfile=qa/results/junit.xml` | `--coverage --coverage-reporter=lcov --coverage-dir=qa/results/coverage` |
| Vitest | `--reporter=default --reporter=junit --outputFile.junit=qa/results/junit.xml` | `--coverage --coverage.reporter=lcov --coverage.reportsDirectory=qa/results/coverage` (`@vitest/coverage-v8`) |
| Jest | `--reporters=default --reporters=jest-junit` + `"jest-junit": {"outputDirectory": "qa/results", "outputName": "junit.xml"}` | `--coverage --coverageReporters=lcov --coverageDirectory=qa/results/coverage` |
| node --test | `--test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=qa/results/junit.xml` | `--experimental-test-coverage --test-reporter=lcov --test-reporter-destination=qa/results/coverage/lcov.info` |
| pytest | `--junitxml=qa/results/junit.xml` | `--cov=<pkg> --cov-report=xml:qa/results/coverage.xml` (pytest-cov) |
| Go | `gotestsum --junitfile qa/results/junit.xml -- ./...` | `go test -coverprofile=qa/results/cover.out ./...` |
| Maven / Gradle | Surefire `target/surefire-reports/TEST-*.xml` / `build/test-results/test/*.xml` | JaCoCo XML report |
| dotnet | `--logger "junit;LogFilePath=<abs>/qa/results/junit.xml"` (JunitXml.TestLogger) | `--collect:"XPlat Code Coverage"` (Cobertura) |
| PHPUnit | `--log-junit qa/results/junit.xml` | `--coverage-cobertura qa/results/coverage.xml` |
| RSpec | `--format progress --format RspecJunitFormatter --out qa/results/junit.xml` | simplecov + simplecov-lcov |
| cargo | `cargo nextest run` with a JUnit profile | `cargo llvm-cov --lcov --output-path qa/results/coverage/lcov.info` |

Reporters/tools above are dev-only dependencies and may be installed. Coverage is optional: if the
coverage tool can't be installed (no network, incompatible version), leave `coverage_command` out
and say so in the worker report.

## 3. Where the new tests go

- Follow the project's convention if it has one (`tests/`, `__tests__/`, `*_test.go` next to the
  code, `src/test/java`, `spec/`). New files get a `qa` marker in the path or name so they are easy
  to find: `tests/qa/orders.create.test.ts`, `tests/qa/test_orders_create.py`,
  `internal/orders/orders_qa_test.go`.
- Shared helpers live in one place: `tests/qa/_support/` (app factory, users/tokens factory, DB
  reset, clock freeze, HTTP mocks). Go: a `qatest` package under `internal/`.
- Existing test files are never edited, moved or deleted. They stay in the full suite.

## 4. Database

Order of preference (decided in Phase 2):

1. **`TEST_DATABASE_URL` exists** (`env.json` → `test_db.found`) **and is safe**
   (`differs_from_database_url: true`, and `local_host: true` or `name_has_test: true`). Use it.
   Found but not safe → tell the user why (booleans only, never the value) and ask
   *Use it anyway, it is a test database* / *Use a throwaway database instead (Recommended)*.
2. **Not found** → ask *Yes, I'll add TEST_DATABASE_URL to .env.test now* / *No, use a throwaway
   database (Recommended)*. On Yes, wait for the user to say it's done, rerun `detect_env.py` and
   check again. Never ask them to paste the URL in chat.
3. **Throwaway database**, matching the engine the app uses (`env.json` → `db_engine`):
   - Docker available → Testcontainers (Node, Python, Go, Java, .NET all have it) or a
     `docker-compose.test.yml` service on a random port, started by the test setup and removed
     after.
   - No Docker → an embedded engine: SQLite temp file (SQLite apps), PGlite or `pg-mem`
     (Postgres, JS), `mongodb-memory-server` (Mongo), H2 in Postgres/MySQL mode only if the ORM
     supports it cleanly. If none fits, the worker reports it and the DB-dependent tests are marked
     `environment` in the report rather than faked with mocks.
   - Schema comes from the project's own migrations (`prisma migrate deploy`, `alembic upgrade
     head`, `migrate up`…), never hand-written.

**Production guard (always):** the test setup refuses to start when the database URL in use equals
`DATABASE_URL` from the non-test env, or the host isn't local and the database name has no `test`
in it (unless the user explicitly accepted it above). Each test run resets data (transaction
rollback per test, or truncate between tests); never `DROP DATABASE` on a URL the skill didn't
create.

## 5. External services

`env.json` → `externals` lists each detected service with `mode`:
- `sandbox` (test-mode keys present, e.g. `sk_test_…`, `*_SANDBOX_*`) → tests may call the
  sandbox for the few flows where the real API matters (payment intent create, webhook signature);
  everything else is still mocked to keep the suite fast.
- `live`, `unknown` or `none` → **mock at the network boundary** (MSW / nock / `respx` /
  `responses` / `httptest.Server` / WireMock). Live keys are never loaded in tests.

Emails, SMS, push: capture in an in-memory outbox; assert on it. Files: temp dir or in-memory
S3 mock (e.g. `aws-sdk-client-mock`, `moto`).

## 6. Determinism

- Freeze the clock where time matters (`vi.useFakeTimers`, `freezegun`/`time-machine`, injected
  clock). If the code reads the real clock with no seam, test with ranges and note it.
- Seeded random data; no reliance on test order; each test creates its own users/data.
- No sleeps longer than what a rate-limit/lockout window needs; prefer a fake clock to waiting.
- Tests must pass or fail the same way on every run; anything that can't be made deterministic is
  listed in the worker report.
