---
name: check-backend-code-quality
description: Readability and extensibility review of a backend/API codebase that writes docs/CODE_QUALITY.md with refactor plans (no code). Finds repeated logic to extract into one function, untyped inputs that need named interfaces/contracts, switch/if-else chains that make adding a new variant (payment method, notification channel, provider, role) painful, long functions/files and deep nesting, dead code and unused dependencies, magic numbers/strings, inconsistent error handling, inconsistent API response shapes and naming, hardcoded dependencies that block testing, and weak or duplicated types across backend/frontend/shared. Ends with an ordered refactor roadmap by impact and effort. Use whenever the user types /check-backend-code-quality (e.g. `/check-backend-code-quality api shared`), or asks how to clean up, refactor, de-duplicate, make their server code easier to read or easier to extend, even if they don't say "code quality". Any language. Report-only; never edits code.
argument-hint: "<api_path> [frontend/shared paths…] [--full]"
---

# /check-backend-code-quality

Input: `$ARGUMENTS` = `<api_path> [extra paths…] [--full]`. Examples: `/check-backend-code-quality api`,
`/check-backend-code-quality server packages/shared`.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded (if none is shown, the folder containing this SKILL.md). `CORE` = `SKILL_DIR/core`.

**CHECKS = `code-quality`** (only the code-quality agent runs; it writes `docs/CODE_QUALITY.md`).

Read `CORE/references/pipeline.md` now and follow it from Phase 0 with that CHECKS value. It covers
the scripts, the agent and the incremental logic (unchanged files are not re-analyzed; fixed problems
disappear from the report), plus the final reply.

Non-negotiables, in case you skim:
- **Plans only:** the report gives plans (what to extract, its name, where it goes, which call sites
  move, in what order). Never code, and never edits to the project.
- **No logic or security judgments:** those belong to `/check-backend-security`.
- **Single agent:** one subagent does the analysis; you coordinate and keep your own context small.
