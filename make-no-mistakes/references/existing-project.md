# Existing-project mode

Used when Phase 0 finds code in the folder. The user wants a feature or change added. Everything in
SKILL.md still applies except what this file overrides. The two priorities are: **touch only what
the feature needs**, and **don't pay to read the repo more than once**.

## Phase 0 additions

- `repo_map.py` has written `mnm/repo-map.md`. Read that file instead of browsing the tree.
- If `mnm/spec.md` exists from an earlier run, read it and `mnm/decisions.md`. The new feature
  extends them; it doesn't restart.
- Find the files that matter with **narrow** Grep/Glob, guided by the map: the routes, models,
  pages and components near the feature, the auth/session module, one representative test, the
  package manifest. Read those, using line ranges for big files. Budget: about 15 files. If you
  need more, the feature is probably several pieces.
- Write `mnm/feature-context.md`:
  - the relevant files with line ranges and one line on why each matters
  - the conventions you observed (naming, error format, test style, folder pattern)
  - the existing auth/ownership mechanism
  - the commands to run tests, lint and build

  This file is what context packs are built from.

## Phase 1–2 overrides

- Research covers the feature: similar products' version of it, UX best practices, and
  implementation and security best practices **for the repo's actual framework and version** (from
  the manifest).
- The interview covers only the feature: its options from research (2a), the scope gap (2b), and
  only the checklist items it affects. Data sharing for any new resource is still mandatory. Don't
  re-ask the UI style if the app already has one; match it. Ask only if the feature introduces a
  new surface, such as a public marketing page in an app that had none.

## Phase 3 overrides

- Keep the existing stack, libraries and versions. No migrations to another framework, no second
  ORM, no new state library when one exists. Add a dependency only when nothing in the repo does
  the job, and name it in the spec.
- Write `mnm/spec.md` as a **feature spec** (or append a `## Feature: <name>` section): acceptance
  criteria, data-model changes (migrations), new access-control rows, new or changed endpoints,
  new or changed pages.
- Contract: if the repo has an OpenAPI file or shared types, extend those, in the repo's own
  location. Otherwise write `mnm/contracts/<feature>.yaml` for the new endpoints only.

## Phase 4 overrides

- Create pieces only for layers the feature touches. A typical set: `backend-<feature>`,
  `frontend-<feature>`, `security-<feature>` (if any backend change), `qa-<feature>`.
  Backend-only feature → no frontend piece.
- **Ownership is file-level, not folder-level:** list the exact files a piece may modify, plus
  globs for the new files it creates, e.g. `backend/app/routers/flashcards.py`,
  `backend/app/models/flashcard.py`, `backend/alembic/versions/*_flashcards*.py`,
  `backend/tests/test_flashcards*.py`. A shared registration file (router include, nav menu) is
  owned by exactly one piece.
- **Context pack** = the slice of `mnm/feature-context.md` for that piece, with line ranges, plus:
  "Copy the pattern of `<file>:<lines>`." Tell the worker explicitly: "The repo is large. Don't
  explore it. Everything you need is listed here."
- Acceptance includes "existing tests still pass": run the existing suite command, not just new
  tests.

## Phase 5–7 overrides

- Ownership check after each piece: `validate_prompts.py --check-ownership <piece>` lists every
  file modified since the piece started that its ownership doesn't cover, after subtracting files
  owned by pieces that ran at the same time. It uses file mtimes, so it works with or without git.
  In a big existing repo this is the guard against "while I was here" edits.
- Security gate:
  - `security_scan.py --root . --api <backend dir> --files <changed backend files>` scans only what
    changed.
  - The `security-<feature>` worker reviews the changed files and their direct callers.
  - Write isolation tests for every new or changed endpoint.
  - Run the existing suite and the new isolation tests.
- QA: e2e tests for the new journeys, plus a smoke run of the existing e2e suite if there is one.
- Final report: list every file changed, grouped by piece, so the user can review the diff quickly.

## Token budget rules (summary)

| Who | Reads |
|---|---|
| Orchestrator | `repo-map.md`, ≈15 targeted files once, worker reports, `worker_status.py` output. Never logs or whole folders. |
| Feature worker | Its prompt + the listed files/line ranges. A narrow Grep only when unavoidable, logged in its report. |
| Security worker | Changed backend files + their direct callers + auth module + hotspots. |
| QA worker | Prompt, e2e folder, the pages/endpoints under test (by URL, not source), reports of the other pieces. |

Fix-ups always `--resume` the same worker session, so it keeps what it already read.
