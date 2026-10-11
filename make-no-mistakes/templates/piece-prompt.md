---
piece: <piece-name>
depends_on:
  - <other-piece>
max_turns: 80
ownership:
  - <glob, e.g. backend/**>
---

# <Piece name>: <one-line purpose>

You are one worker in a larger build. The orchestrator wrote this brief; other workers own other
parts of the repo at the same time. Everything you need is here or in the files listed under
Context pack.

## Goal condition

```text
Implement mnm/prompts/<this file> completely (read it first; it is your full brief).
The goal is met only when this session's transcript shows ALL of:
1. `<check command>` with exit code 0 and 0 failed tests.
2. `<lint/typecheck command>` with exit code 0.
3. `<extra runtime proof>`.
4. `python "<SKILL_DIR>/scripts/validate_prompts.py" --root . --check-ownership <piece-name>` printing "ownership: clean".
5. mnm/reports/<piece-name>.md written with every acceptance ID marked PASS plus the proving command, then printed with `cat`.
6. Every file in mnm/answers/<piece-name>/ listed under "Answers applied" in that report.
Never weaken, skip or delete a test to make it pass. Or stop after <max_turns> turns with the report listing what is unfinished.
```

## Context pack

**Project:** <name>: <one line>. Stack: <backend stack> / <frontend stack>. Repo layout:
`backend/`, `frontend/`, `e2e/`.

**Read these files (and nothing else unless a step below needs it):**
- `mnm/contracts/openapi.yaml`: only paths `<…>` and schemas `<…>`
- `<file>` (<why>)

**Do not read:** `<other piece dirs>`, `node_modules/`, lockfiles, generated files, `mnm/logs/`.

**Spec excerpt:**
<acceptance-relevant features, copied from mnm/spec.md>

**Data model (this piece):**
<tables/fields/indexes/constraints>

**Access-control rows (this piece):**
| Resource | Action | Owner | Other user | Anonymous | Admin | Rule |
|---|---|---|---|---|---|---|

**Design tokens (frontend pieces only):**
<tokens block>

## Ownership

You may create or modify only files matching:
- `<glob>`

Everything else is read-only. Need a change elsewhere, e.g. to the API contract? Write a question
with `"kind": "contract"` and continue with the current contract.

## Acceptance

- **A1** <criterion>. Verify: `<command or test id>`
- **A2** …

## Best practices

- <one actionable line each, from mnm/research.md and the skill references>

## Constraints

- Follow the stack and conventions above. Add a dependency only when the brief needs it, use the
  latest stable version, and name it in the report.
- Secrets come from the environment only. Add new variables to `.env.example` through a question if
  you don't own it.
- <piece-specific constraints>

## Questions

If something is ambiguous, don't stop. Pick the recommended option, record it in
`mnm/assumptions.md` (`- [<piece-name>] <assumption>`), and write
`mnm/questions/<piece-name>-<n>.json`:
`{"id": "<piece-name>-<n>", "piece": "<piece-name>", "kind": "product|contract", "question": "...", "options": ["recommended…", "…"], "recommended": "...", "assumption_taken": "..."}`.
At the start of each turn, check `mnm/answers/<piece-name>/` and apply any new answer.

## Report

Write `mnm/reports/<piece-name>.md`, at most ~60 lines:

```markdown
# <piece-name>: <achieved|partial>
## Acceptance
| ID | Status | Proof (command → result) |
## How to run / test
## Files created or changed (paths only)
## Dependencies added
## Answers applied
## Assumptions taken
## Unfinished / risks
```
