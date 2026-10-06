# backend-checker pipeline (orchestrator)

You coordinate. Scripts do the indexing, diffing, vulnerability lookups and report rendering. Agents
read code and write findings JSON. You never read the whole repo into your own context unless the
health-mode preload says so, and you never paste report contents back to the user.

`CORE` = `<SKILL_DIR>/core`. Run every script from the project root (the current working directory)
as `python "CORE/scripts/<name>.py" --root . …`. They use only the Python standard library.
`CHECKS` comes from the SKILL.md that sent you here: one id for a single check, every registry id for
health.

## Why it is built this way
- **Cost.** A backend can be hundreds of files. Every token an agent reads costs money and time, so:
  - scripts build an index once;
  - unchanged files are not re-analyzed (incremental mode);
  - in health mode the code is read once and shared through the prompt cache.
- **Privacy.** The reports are a map of the user's weaknesses, so everything stays gitignored and
  secrets are masked.

## Phase 0 – Arguments
`$ARGUMENTS` = `<api_path> [extra paths…] [--full]`.
- The first path is the API directory. Any further paths are optional context (frontend, shared
  types); don't ask the user to label them.
- `--full` disables incremental mode.
- If the API path is missing or doesn't exist, look for likely candidates (`api/`, `server/`,
  `backend/`, `src/` with a server framework in its manifest) and ask with AskUserQuestion. Never
  guess silently.

## Phase 1 – Preflight (scripts only)
Run in this order. Each prints a compact JSON summary; that summary is all you need. Don't open
`index.json`: it's large and the agents get the parts they need from their plan.
1. `ensure_gitignore.py --root .` adds the reports and `docs/.backend-checks/` to `.gitignore`. If it
   lists `tracked` files, tell the user at the end to run `git rm --cached <file>`. Never run it yourself.
2. `index.py --root . --api <api_path> [--extra <paths…>]`.
3. `plan.py --root . --checks <comma-separated CHECKS> [--full]`.
4. If `all_skip` is true, nothing changed since the last run: go straight to Phase 4. No agents.
5. Run every `prep_commands` entry of the non-skipped checks. Independent commands go in parallel
   Bash calls in one message.
   - `osv_check.py` needs the network. If it reports `network_ok: false`, carry on: the security agent
     falls back to WebSearch for 1a.
6. Delete leftover `docs/.backend-checks/findings-*.new.json` files from interrupted runs.

## Phase 2 – Agents
Skip any check whose plan says `skip: true`.

**Prompt for a normal subagent** (fill in the placeholders):
```
You are the <title> agent of backend-checker, checking the backend of the project at <absolute project root>.
Work from that directory. Read <CORE>/agents/agent-contract.md, then your brief <CORE>/agents/<id>.md, and follow them.
Your plan: docs/.backend-checks/plan-<id>.json. Write: docs/.backend-checks/findings-<id>.new.json.
The code is NOT in your context: load it with bundle.py as the contract describes.
Return only the one-line summary from the contract.
```

**One check** (`/check-backend-security`, `/check-backend-code-quality`): spawn one `general-purpose`
subagent with the prompt above.

**Health** (`/check-backend-health`):
- **If `preload.ok` is true and the Agent tool offers a `fork` subagent type** (a fork inherits your
  context, so whatever you read now is a cheap cache read for every child instead of a fresh input):
  1. Run `bundle.py --root . --plans <plan file of every non-skipped check>`.
  2. Read every part it lists, plus `CORE/agents/agent-contract.md`, in one message (parallel Read
     calls).
  3. In **one message**, spawn one `fork` per non-skipped check:
     ```
     You are the <title> agent of backend-checker. The bundle parts and the agent contract above are already in your context:
     do not read those files again. Read your brief <CORE>/agents/<id>.md and follow it with the contract.
     Your plan: docs/.backend-checks/plan-<id>.json. Write: docs/.backend-checks/findings-<id>.new.json.
     Return only the one-line summary from the contract.
     ```
- **Otherwise** (budget exceeded or no fork type): spawn one `general-purpose` subagent per
  non-skipped check, all in one message so they run in parallel, with the normal prompt.

**No Agent tool** (e.g. you are yourself running as a subagent): do each check yourself, one after
another, following the contract and the brief. Load the bundle once and reuse it for every check.

**Spawn agents in the foreground** (`run_in_background: false`). Your next step needs their output,
and several Agent calls in one message still run in parallel. A background agent can outlive you when
you yourself run as a subagent, and then nothing gets merged.

While agents run, wait. Don't read their files and don't do their work.

**If an agent dies on an infrastructure error** (network/API error, ENOTFOUND, overload) before
returning, spawn it again once with the same prompt, adding: "A previous attempt was interrupted.
Bundle parts and tests.json/tests.log from it may already exist; reuse them instead of re-running the
tests." Preflight and prep outputs stay valid, so don't redo Phase 1. If the retry fails too, tell the
user which check didn't finish and render only the others.

## Phase 3 – Merge and questions
1. For each check that ran: `findings.py merge --root . --check <id>`.
   - **If it fails on validation**, send the errors to that agent (SendMessage) to fix. If the agent
     is gone, fix only structural problems yourself (a wrong section id, a missing severity). Never
     invent or remove findings.
   - Merge drops findings in re-analyzed files and rerun sections, carries the rest over and removes
     fixed ones. The report never mentions fixed items.
2. `findings.py questions --root . --check <id>` for each check. If there are questions, ask them with
   AskUserQuestion, up to 4 per call:
   - header `4a`;
   - question text = the item's question plus its `where`;
   - options: **Intended – ignore** · **Not intended – report** · **Not sure – report as Low**.

   Map the answers to `intended` / `report` / `unsure` and record them all with
   `findings.py decide --root . --check <id> --answers '{"<fingerprint>": "<answer>", ...}'`.
   Answers are stored in `docs/.backend-checks/decisions.json`, so the same question is never asked
   again. If you can't ask (non-interactive run), leave them: the report marks them *Needs your answer*.

## Phase 4 – Render and reply
1. `findings.py render --root . --check <id>` for every check in CHECKS. This also covers skipped
   checks, so their header says nothing changed. Its output already has everything the reply needs:
   counts per level, `top` items, `tests` status and `mode`. Don't open the report to write the reply.
   Counts can differ from an agent's summary line, because answered 4a questions drop or downgrade
   items.
2. Reply briefly. **Don't paste the reports.** Include:
   - one line per report: a link to the file and its counts by level (from the render output);
   - **Fix first:** the 3–5 most severe security items (id + title) and the top 3 roadmap items for
     code quality;
   - test status (ran / failed / not run / no suite);
   - anything the user must act on: tracked report files (`git rm --cached`), secrets to rotate,
     OSV/network fallbacks, unanswered questions;
   - the mode (full / incremental with N files / unchanged).

## Rules
- Read-only on the project. The only writes are `docs/` reports, `docs/.backend-checks/*` and the
  `.gitignore` lines.
- No installs, no docker, no git commands that change anything.
- Only package names and versions go to external services.
- Talk to the user in the language they use. Reports are written in English.
