---
name: make-no-mistakes
description: Plans a software project in depth and then builds it end to end with parallel /goal workers. Researches similar products and best practices on the web, interviews the user with selectable options (feature-by-feature Yes / No / Yes with a tweak, then detail rounds; never architecture questions), picks the stack itself, writes mnm/spec.md, an API contract and /goal-ready prompt files (foundationprompt.md, backendprompt.md, frontendprompt.md, securityprompt.md, qa.md…), runs them as headless `claude -p "/goal …"` workers in waves, relays worker questions to the user while they keep working, enforces a strict security gate (no user can reach another user's data) and an SEO-ready, polished UI, and finishes with a working, verified app. In an existing project it adds the requested feature touching only the files it needs, with token-efficient context packs. Use whenever the user types /make-no-mistakes (e.g. `/make-no-mistakes build me an app for learning german`), or asks to plan and fully build an app, website, SaaS or feature "from scratch", "end to end", "without mistakes", or wants a detailed plan split into /goal prompts executed by subagents.
argument-hint: "<what to build, e.g. 'build me an app for learning german'>"
---

# /make-no-mistakes

Input: `$ARGUMENTS`, a short description of what to build (new project) or what to add (existing
project). Empty → resume from `mnm/state.json` if it exists, otherwise ask what to build.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded. Scripts are
`python "SKILL_DIR/scripts/<name>.py"` (standard library only). Read each reference file when you
reach the phase that points to it, not all up front.

You are the **orchestrator**. You research, interview, decide, write the plan and supervise. Workers
(headless `claude -p "/goal …"` sessions) write the code. You stay responsive to the user the whole
time, so the user can answer worker questions while the workers keep going.

## Hard rules

1. **Never ask about architecture.** Languages, frameworks, databases, hosting, libraries, folder
   layout, API style: you decide with `references/stack-selection.md`. Ask about the *product*:
   features, users, data sharing, look and feel, scope.
2. **Options, not essays.** Every question is AskUserQuestion with 2–4 options, the recommended one
   first and labelled "(Recommended)". Only two places expect typed text: the open "what else?"
   question (2b) and a tweak. Batch up to 4 questions per call.
3. **Security is non-negotiable.** No user may read or change another user's data unless the spec
   says it is shared. The security gate (Phase 6) and the isolation test matrix can't be skipped,
   shortened or marked "pending".
4. **Never touch git.** No init, add, commit, branch, stash, reset or push. Read-only commands
   (`git status`, `git diff --name-only`, `git ls-files`) are fine. Editing `.gitignore` is a file
   edit and is required (Phase 0).
5. **Never fabricate** testimonials, stats, prices, legal facts, company details or content claims.
   Use `{{PLACEHOLDER: snake_case_name}}` and list every placeholder in the final report.
6. **Token discipline** (applies to you and to every worker):
   - One full-repo pass only (`repo_map.py`), never repeated.
   - Research once, then hand workers excerpts.
   - The API contract is written before workers start, so pieces never read each other's code.
   - Every worker gets a context pack listing exactly what to read; workers don't explore.
   - You read `worker_status.py` summaries and `mnm/reports/*.md`, never raw logs or whole codebases.
   - Fixes go to the same worker session with `--resume` instead of a new worker.
7. **Talk in the user's language.** Write code, prompts and the spec in English. UI copy uses the
   target language(s) from the interview.

## Phase 0: Preflight

1. **Resume.** If `mnm/state.json` exists, read it and continue from its `phase`. Don't re-ask
   answered questions (they're in `mnm/spec.md` and `mnm/decisions.md`).
2. **CLI check.** Run `claude --version`; it must be ≥ 2.1.259 (`/goal` headless +
   `--permission-prompts`). Older → tell the user to update and stop.
3. **Gitignore.** Run `python "SKILL_DIR/scripts/ensure_gitignore.py" --root .`. It adds `/mnm/` and
   `.env*` (keeping `!.env.example`). If it reports `tracked_files`, tell the user to run
   `git rm -r --cached mnm` themselves.
4. **Mode.**
   - **New:** the folder is empty or holds only README/LICENSE/.git/.gitignore/mnm.
   - **Existing:** anything else. Run `python "SKILL_DIR/scripts/repo_map.py" --root .` once. It
     writes `mnm/repo-map.md` (stack, tree with line counts, entry points, routes, models, auth,
     test/build/lint commands) and prints a short summary. Then read
     `references/existing-project.md`, which overrides parts of Phases 1–7.
5. Create `mnm/state.json` with `{"phase": "research", "mode": "new|existing", "idea": "<args>"}`.
   Update `phase` at the end of every phase.

## Phase 1: Research (read `references/research.md`)

Send 3–5 WebSearch calls **in one message** (standard mode; extended only when results are thin):
- similar products and competitors
- their feature lists and reviews
- what users complain about
- domain best practices
- in existing mode: best practices for the feature on the repo's stack and version

Add what you already know. Write `mnm/research.md`:
- **feature catalog:** id, feature, who has it, how they do it, source
- **gaps competitors leave open**
- **best-practice notes**, grouped by piece (backend, frontend, security, SEO, domain)

## Phase 2: Interview (read `references/interview.md`)

- **2a Features from research.** One question per catalog feature, 4 per AskUserQuestion call,
  repeated until done. Options, in order:
  - **Yes** ("build it like <competitor> does")
  - **No** (skip it)
  - **Yes, with a tweak**: the user writes the tweak in the free-text box. If they pick it with no
    text, ask one short follow-up for the tweak.
- **2b Scope gap.** Is the description still unclear about what else to build? Then ask one plain
  text question, "What else should it do?", and wait for the typed answer. Skip it when it's clear.
- **2c Detail rounds.** Walk the completeness checklist in `interview.md`. Each round asks only open
  items, with recommended options. Repeat until every item is answered or explicitly defaulted.
  Always ask:
  - the **data-sharing questions** (they define the access-control matrix)
  - the **UI style**: Professional / Balanced / Fun
- **2d Confirm.** Show a one-screen summary (features with tweaks, roles, sharing rules, style,
  scope), then AskUserQuestion: "Build this (Recommended)" / "Change something". Loop on changes.

Record every answer in `mnm/decisions.md` as you go, so a resume never re-asks.

## Phase 3: Architecture and spec (read `references/stack-selection.md`; no questions)

1. Score backend size and frontend size with the rubric, then pick the stack. Write the choice and
   the one-line reason to `mnm/decisions.md`. Don't ask the user to confirm the stack.
2. Write `mnm/spec.md` from `SKILL_DIR/templates/spec.md`:
   - features with numbered acceptance criteria
   - roles
   - data model
   - the **access-control matrix**
   - page list with each page's search intent
   - design tokens for the chosen style
   - non-functional targets
3. Write `mnm/contracts/openapi.yaml`: every endpoint, schema, auth requirement and error shape.
   This is the single source of truth between backend and frontend, and only you edit it.

## Phase 4: Decompose into /goal prompts (read `references/prompt-format.md`)

1. Split the work into pieces and waves (`prompt-format.md` has the default wave plan and sizing).
2. Write one `mnm/prompts/<piece>prompt.md` per piece from `SKILL_DIR/templates/piece-prompt.md`.
   - Front matter: `piece`, `depends_on`, `max_turns`, `ownership` globs.
   - Sections, in order:
     - **Goal condition** (≤ 4,000 chars, measurable, evidence shown in the transcript)
     - **Context pack**
     - **Ownership**
     - **Acceptance** (each with a verify command)
     - **Best practices**
     - **Constraints**
     - **Questions**
     - **Report**
   - Write `SKILL_DIR` as the real absolute path, because workers run the ownership check with it.
   - The QA piece is `mnm/prompts/qa.md`.
3. Run `python "SKILL_DIR/scripts/validate_prompts.py" --root .`. Fix every error it prints:
   missing sections, condition too long, overlapping ownership, unknown dependency, cycle. It
   prints the wave order and stores it in `mnm/state.json`.
4. Show the user a short piece/wave table for information.
5. Ask the one runtime question (consent, not architecture), "How should workers run?":
   - **Auto mode (Recommended):** a classifier approves each action; unattended.
   - **Accept edits + allowlist:** file edits are auto-approved, and only the stack's
     build/test/install commands are allowed.
   - **Stop here:** keep the plan, build later.

   Record the answer as `worker_mode` (`auto` / `acceptEdits`) in `mnm/state.json`.

## Phase 5: Execute and supervise

Start every piece of the current wave **in one message**, each as its own Bash call with
`run_in_background: true`:

```
python "SKILL_DIR/scripts/launch_worker.py" --root . --piece <piece> --mode <auto|acceptEdits> --skill-dir "SKILL_DIR"
```

What the launcher does:
- Reads the goal condition from the prompt file and runs `claude -p "/goal <condition>"`.
- Appends the worker contract, sets `--permission-prompts none`, and streams stream-json output to
  `mnm/logs/<piece>.jsonl`.
- Records `session_id` and status in `mnm/state.json`, reading the evaluator's verdict from the
  session transcript.
- You are notified when it exits.

Two warnings:
- **Always go through `launch_worker.py`.** Never type `claude -p "/goal …"` into Git Bash
  yourself: MSYS path conversion rewrites `/goal` to `C:/Program Files/Git/goal`, and the goal
  silently never gets set.
- Background commands have no time limit in your interactive session, so a long worker is fine.

**While workers run:**
- Start a Monitor on `python "SKILL_DIR/scripts/worker_status.py" --root . --watch`.
  - It prints `QUESTION …` and `STATUS piece → status` lines as they happen.
  - It ends itself after 29 minutes (`WATCH_END`; start it again while workers run) or when
    nothing is running (`IDLE`).
  - No Monitor tool? Run `worker_status.py --root . --questions` whenever you get control.
- `python "SKILL_DIR/scripts/worker_status.py" --root .` gives a one-screen overview: waves,
  statuses, costs, open questions.
- Each question file has: question, options, recommended, assumption taken, piece. Ask the user
  with AskUserQuestion, then write `mnm/answers/<piece>/<question-id>.md`.
- Workers never block on a question: they continue with the recommended assumption and apply
  answers as they arrive.
- **Contract-change requests** (`"kind": "contract"`) are yours to decide. Update
  `mnm/contracts/openapi.yaml`, then write an answer to every affected piece.

**When a worker exits:** run `python "SKILL_DIR/scripts/worker_status.py" --root . --piece <piece>`,
then read `mnm/reports/<piece>.md`.

| Status | Action |
|---|---|
| `achieved` | Run `python "SKILL_DIR/scripts/validate_prompts.py" --root . --check-ownership <piece>`. It lists files modified since the piece started that match neither its ownership nor the ownership of a piece that ran at the same time. Violations → `--resume` the worker with an instruction to revert them. |
| `not_met` (stopped unmet: turn cap or no progress) / `impossible` / `error` / `ended` (no verdict) | Read the verdict reason in `worker_status.py` and the report. Fix the prompt, ask the user, or split the piece. Then `launch_worker.py --resume --message "<what to do next>"`: same session, nothing re-read. |
| Answer differs from the assumption the worker took, after it finished | `launch_worker.py --resume --message "<what to change>"`. The message is saved as an answer file **and** added to the resumed goal condition, so the evaluator only accepts the goal once the fix-up is visibly done. |

A wave is done when every piece in it is `achieved` and ownership-clean. Then start the next wave.

## Phase 6: Security gate (read `references/security.md`) — after the backend wave, mandatory

1. Right before launching the security wave, run
   `python "SKILL_DIR/scripts/security_scan.py" --root . --api <backend dir> --frontend <frontend dir>`.
   It writes
   `mnm/security-hotspots.json`: routes without an auth dependency, queries without an
   owner/tenant filter, ids taken from the client, secrets, wildcard CORS, missing headers and
   rate limits, raw SQL, stack-trace leaks.
2. The `security` piece is a fresh worker, never the one that wrote the backend. Its prompt
   (`securityprompt.md`, written in Phase 4) makes it:
   - review against `security.md` and the hotspots
   - write `mnm/reports/security.md`
   - generate and run the **isolation test matrix** from the spec's access-control matrix
   - fix findings until there are zero Critical/High and the matrix passes
3. Verify it yourself:
   - rerun the isolation tests and the dependency audit command
   - read **only** the handlers named in the report's Critical/High findings and in the hotspots
   - any doubt → `--resume` the security worker with the exact concern

   The gate passes only when you have seen the passing output yourself.

## Phase 7: Integration, QA and final verification

1. Run the remaining waves (integration/SEO, then `qa`) the same way as Phase 5.
2. Start the app with the commands the foundation report gives. Smoke-test it in the built-in
   browser at 390 px and 1280 px:
   - sign up / sign in
   - each main journey
   - a second user cannot see the first user's data
3. Run `python "SKILL_DIR/scripts/seo_check.py" <frontend-url> --sitemap`. Leftover
   Critical/High SEO issues → `--resume` the owning worker.
4. Any failure → `--resume` the owning piece with the failing output. Repeat until clean.
5. Make sure the project README has setup, env vars, run, test and deploy notes. The foundation
   piece owns README.md.

## Phase 8: Report

Set `phase: "done"`. Reply in the user's language with:
1. **What was built:** features (and tweaks), stack plus the one-line reason, how to run it.
2. **Security:** isolation matrix result (N endpoints × 4 actors, all pass), audit results, fixed
   findings count.
3. **Assumptions workers made** (from `mnm/assumptions.md`) that the user hasn't confirmed.
4. **Open placeholders:** file and what is needed.
5. **Pending:** anything that needs deployment or credentials (real OAuth keys, payment keys,
   PageSpeed on a live URL).
6. **Ideas:** competitor features the user said No to, or gaps worth a later run. Suggestions only.

`mnm/` keeps everything (spec, prompts, reports, logs), so a later `/make-no-mistakes add X` builds
on it in existing-project mode.
