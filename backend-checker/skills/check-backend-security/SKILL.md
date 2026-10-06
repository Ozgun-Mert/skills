---
name: check-backend-security
description: Security audit of a backend/API codebase that writes docs/SECURITY_PROBLEMS.md. Checks vulnerable or end-of-life dependencies (live OSV lookup), secrets in git or exposed to the frontend, SQL/NoSQL injection, broken access control (IDOR, mass assignment), trusting frontend prices, password storage and weak crypto, data over-exposure, upload safety, CORS, security headers/helmet, rate limiting, idempotency (double payments), user enumeration, JWT/session flaws, CSRF, SSRF/command injection, error leakage, secrets in logs, payment webhooks, WebSocket auth, plus failing tests, risky DB operations and crash-prone logic. Use whenever the user types /check-backend-security (e.g. `/check-backend-security api web shared`), or asks to security-review, pentest-style audit, or "find vulnerabilities" in their server, API or backend code, even if they don't say "audit". Any language or framework. Report-only; never edits code.
argument-hint: "<api_path> [frontend/shared paths…] [--full]"
---

# /check-backend-security

Input: `$ARGUMENTS` = `<api_path> [extra paths…] [--full]`. Examples: `/check-backend-security api`,
`/check-backend-security server web packages/shared`.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded (if none is shown, the folder containing this SKILL.md). `CORE` = `SKILL_DIR/core`.

**CHECKS = `security`** (only the security agent runs; it writes `docs/SECURITY_PROBLEMS.md`).

Read `CORE/references/pipeline.md` now and follow it from Phase 0 with that CHECKS value. It covers
the scripts, the agent and the incremental logic (unchanged files are not re-analyzed; fixed problems
disappear from the report), plus the 4a questions and the final reply.

Non-negotiables, in case you skim:
- **Read-only:** never edit the project's code, never install anything, never change git state.
- **Never print secret values**: reports are gitignored and masked.
- **Single agent:** one subagent does the analysis; you coordinate and keep your own context small.
