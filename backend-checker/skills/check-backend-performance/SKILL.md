---
name: check-backend-performance
description: Performance and cost review of a backend/API codebase that writes docs/PERFORMANCE.md with numbered, prioritized fixes (plans, no code). Finds slow SQL (N+1, writes in loops, SELECT *, two queries where one is enough, filtering/paging in code, deep OFFSET, non-sargable WHERE), worse-than-needed algorithmic complexity (O(n²) loops, hand-written sorts, missing memoization), missing caching for hot rarely-changing data, architecture fit (database, language, framework and libraries for the project's scale, researched online), cross-region latency between backend, database and Redis (reads deployment config and measures the live URL), missing/redundant indexes, unbounded lists and big payloads, blocking work in async code, connection pooling and timeouts, memory growth, external API calls in loops, HTTP caching/CDN and cold starts. Use whenever the user types /check-backend-performance (e.g. `/check-backend-performance api --url https://api.example.com`), or asks why their backend/API is slow, how to speed it up, optimize queries, reduce latency, server cost or memory, even if they don't say "performance". Any language or framework. Report-only; never edits code.
argument-hint: "<api_path> [frontend/shared paths…] [--url https://your-domain] [--full]"
---

# /check-backend-performance

Input: `$ARGUMENTS` = `<api_path> [extra paths…] [--url <public URL>] [--full]`. Examples:
`/check-backend-performance api`, `/check-backend-performance server web --url https://api.example.com`.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded (if none is shown, the folder containing this SKILL.md). `CORE` = `SKILL_DIR/core`.

**CHECKS = `performance`** (only the performance agent runs; it writes `docs/PERFORMANCE.md`).

Read `CORE/references/pipeline.md` now and follow it from Phase 0 with that CHECKS value. It covers
the scripts, the project-profile questions, the agent and the incremental logic (unchanged files are
not re-analyzed; fixed problems disappear from the report), plus the final reply.

Non-negotiables, in case you skim:
- **Plans only:** never code, and never edits to the project.
- **Security and readability belong elsewhere:** `/check-backend-security` and
  `/check-backend-code-quality` cover them.
- **Live probing stays light:** GET requests to the user's own URL only (at most 8), TCP connects
  without logging in, and IP addresses to one geo-IP lookup. Credentials from `.env` files are never
  read into the report.
- **Single agent:** one subagent does the analysis; you coordinate and keep your own context small.
