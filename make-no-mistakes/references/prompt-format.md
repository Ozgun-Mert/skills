# Decomposing into /goal prompts (Phase 4)

Each piece is run by one headless worker: `claude -p "/goal <Goal condition>"`, with
`worker-contract.md` appended to its system prompt. The worker sees only three things: the
condition, the contract, and what it reads. So every piece prompt must be **complete on its own**
and **cheap to start**.

## How /goal judges a piece (design the condition around this)

- After every turn, a small model reads the conversation and decides: not met / met / impossible.
- It **can't** run commands or read files. A criterion counts only when its evidence (command
  output, exit code, file listing) is **printed in the worker's transcript**.
- The condition can be at most 4,000 characters. Keep it to about 1,500. Details belong in the
  prompt file; the condition points there and names the proof.
- Add a turn cap so a stuck worker ends: "…or stop after N turns, writing what is left to the
  report".

### Condition template

```text
Implement mnm/prompts/<file> completely (read it first; it is your full brief).
The goal is met only when this session's transcript shows ALL of:
1. `<check command 1>` output with exit code 0 (e.g. `cd backend && uv run pytest -q` → 0 failed).
2. `<check command 2>` exit code 0 (lint + typecheck).
3. `<extra proof>` (e.g. `curl -s localhost:8000/health` → {"status":"ok"}).
4. `python <SKILL_DIR>/scripts/validate_prompts.py --root . --check-ownership <piece>` printing "ownership: clean".
5. mnm/reports/<piece>.md written, with every acceptance ID (A1…An) marked PASS and the command that proved it, then printed with `cat`.
6. Every file in mnm/answers/<piece>/ listed under "Answers applied" in that report.
Never weaken, skip or delete a test to make it pass. Or stop after <N> turns with the report listing what is unfinished.
```

`<SKILL_DIR>` is written as the real absolute path when the prompt is generated.

Turn caps: foundation 40 · backend/frontend piece 80 · security 60 · integration 60 · qa 80.

## Default wave plan (new project)

| Wave | Piece (file) | Depends on | Owns | Done when |
|---|---|---|---|---|
| W0 | `foundation` (`foundationprompt.md`) | — | root files (`docker-compose.yml`, `.env.example`, `README.md`, `Makefile`), `backend/` skeleton, `frontend/` skeleton | both packages install; `check` scripts run green on empty code; DB starts; `/health` OK; frontend dev server renders a placeholder; API types generated from the contract |
| W1 | `backend` (`backendprompt.md`) | foundation | `backend/**` | every endpoint in the contract implemented and covered by tests, including owner-scoping tests |
| W1 | `frontend` (`frontendprompt.md`) | foundation | `frontend/**` | every page in the spec built with the design tokens, against the typed client in mock mode; SEO metadata per page; build + typecheck + component tests green |
| W2 | `security` (`securityprompt.md`) | backend | `backend/**`, `mnm/reports/security.md` | zero Critical/High findings; isolation matrix tests pass; dependency audit clean |
| W3 | `integration` (`integrationprompt.md`) | frontend, security | `frontend/**` | mocks off, real API, auth flows work, errors handled; `seo_check.py` clean |
| W4 | `qa` (`qa.md`) | integration | `e2e/**`; may fix bugs anywhere | Playwright journeys + cross-user e2e pass; all packages' `check` green |

The same piece may appear in more than one wave only with a dependency path between them.
Overlapping ownership is legal only when one piece (transitively) depends on the other, so the two
never run at the same time. `validate_prompts.py` enforces this.

### Optional pieces (add only when the spec needs them)

| Piece | When | Depends on | Owns |
|---|---|---|---|
| `payments` | Monetization ≠ free | backend | `backend/**/payments*`, `backend/**/billing*`, webhook route |
| `notifications` | Emails/reminders/jobs | backend | jobs/worker module, email templates |
| `admin` | Admin needs | backend (+ frontend) | admin routes/pages |
| `i18n` | > 1 UI language | frontend | `frontend/**/i18n*`, `frontend/messages/**` |

These run in W2 next to security when they own separate files. Otherwise give them their own wave.
Security must then also depend on them, so the gate reviews their code.

### Splitting big pieces

A piece should fit in its turn cap: about ≤ 25 new files or ≤ 8 endpoint groups. Split when it's
larger:
- **Backend (large/Go):** `backend-core` (config, db, auth, middleware, users) in W1. Then
  `backend-<domain>` pieces in W1b, in parallel, each owning
  `backend/internal/<domain>/**` + `backend/queries/<domain>.sql` + `backend/migrations/*_<domain>_*`.
  Shared files (router registration, `sqlc.yaml`) stay with `backend-core`. Domains add themselves
  through a registration file each, e.g. `backend/internal/http/routes_<domain>.go`.
- **Frontend (Next.js, many pages):** `frontend-shell` (layout, design system, nav, auth pages)
  first. Then `frontend-public` (marketing/SEO pages) ∥ `frontend-app` (logged-in area), split by
  route groups (`app/(marketing)/**` vs `app/(app)/**`).

## Prompt file format (`mnm/prompts/<piece>prompt.md`, QA = `mnm/prompts/qa.md`)

Use `SKILL_DIR/templates/piece-prompt.md`. The front matter is parsed by the scripts. Keep the keys
and list syntax exactly as shown:

```markdown
---
piece: backend
depends_on:
  - foundation
max_turns: 80
ownership:
  - backend/**
---
```

Required sections, in order:
`## Goal condition` (one ```text fence) · `## Context pack` · `## Ownership` · `## Acceptance` ·
`## Best practices` · `## Constraints` · `## Questions` · `## Report`.

### Context pack: what makes workers cheap

- **Read these files:** an explicit list. In existing mode, add line ranges, e.g.
  `backend/app/routers/decks.py:1-80 (pattern to copy)`.
- **Contract slice:** "In `mnm/contracts/openapi.yaml` read only paths `/decks*`, `/cards*` and
  schemas `Deck`, `Card`, `Error`." The frontend gets the same slice, so neither reads the other's
  code.
- **Spec excerpts pasted inline:** the acceptance criteria, the rows of the access-control matrix
  for this piece's resources, the data model tables it owns, and the design tokens (frontend).
- **Best practices pasted inline** from `mnm/research.md`, only the lines for this piece.
- **Do not read:** list the big or irrelevant folders, e.g. `frontend/**` for backend,
  `node_modules`, lockfiles and generated files.

### Acceptance

Number every criterion `A1…An`. Each has a verify command, e.g.
`A3 Owner scoping: GET /decks/{id} of another user returns 404 — test test_decks.py::test_other_user_cannot_read`.
Every row of the access-control matrix that touches this piece's resources becomes an acceptance
row.

## Validation (`validate_prompts.py`)

It checks:
- front matter and section presence
- condition length ≤ 4,000 chars
- `depends_on` names exist and have no cycles
- ownership overlaps are only allowed along dependency paths
- the condition mentions the report and the ownership check

It writes `waves` into `mnm/state.json` and prints the wave table. Fix every error before launching
anything.
