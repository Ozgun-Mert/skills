---
name: check-backend-health
description: Full backend health check that runs every registered backend check at once, in parallel: the security audit → docs/SECURITY_PROBLEMS.md, the code-quality review → docs/CODE_QUALITY.md, the performance review → docs/PERFORMANCE.md, plus any check added later. It builds the index once, reads the code once and shares it between the agents where the environment allows. Incremental: unchanged files aren't re-analyzed and fixed problems vanish from the reports. Use whenever the user types /check-backend-health (e.g. `/check-backend-health api web shared --url https://api.example.com`), or asks for a full backend/API review, audit, health check, or "check everything" on their server code, even without naming the reports. Any language or framework. Report-only; never edits code.
argument-hint: "<api_path> [frontend/shared paths…] [--url https://your-domain] [--full]"
---

# /check-backend-health

Input: `$ARGUMENTS` = `<api_path> [extra paths…] [--url <public URL>] [--full]`. Example: `/check-backend-health api web shared`.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded (if none is shown, the folder containing this SKILL.md). `CORE` = `SKILL_DIR/core`.

**CHECKS = every check in `CORE/registry.json`.** Pass `--checks all` to `plan.py`. The registry is
the single list of checks, so a check added later runs here automatically. Each check writes its own
report (`output_md` in the registry).

Read `CORE/references/pipeline.md` now and follow it from Phase 0 with that CHECKS value. Use the
**Health** branch of Phase 2:
1. Read the bundled code once yourself.
2. Fork one agent per check in a single message, so the agents share that code from the prompt cache
   instead of each re-reading the repo.
3. Fall back to parallel general-purpose subagents when forking isn't possible or the preload budget
   is exceeded.

Non-negotiables, in case you skim:
- **Read-only:** never edit the project's code, never install anything, never change git state.
- **Shared prep:** tests run once (inside the security check) and the index is built once for all
  checks.
- **Short reply:** keep it to counts, the few items to fix first and actions for the user. Don't
  paste the reports.
