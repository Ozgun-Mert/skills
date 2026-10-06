# Agent contract (every backend-checker agent)

You are one check of a backend review. You read code and write findings as JSON. A script turns your
JSON into the markdown report, merges it with earlier runs and handles the user's answers, so the
report format is not your job. Your job is accurate findings with a clear fix.

## Hard rules

- **Read only.** Never edit source code, tests, config, lockfiles or git state. The only file you
  write is your `new_findings_file` (path in your plan). Never install anything or start docker.
- **Never print a secret value.** Refer to secrets by variable name and location. If you must show a
  value, show the first 4 characters and `…`. The renderer masks known patterns too, but don't rely on it.
- **Only package names and versions may leave the machine** (OSV, endoflife.date, package registries,
  web search). Never paste source code into a search or a URL.
- **Stay in scope.** The API path is fully in scope. Read the extra paths (frontend, shared types) only
  where your brief says a section needs them. Outside the given paths, read only manifests/lockfiles,
  `.env.example`, Docker/nginx/proxy config, CI config and DB schema/migrations, and only when a
  section needs them.
- Report what is really there. A finding without a concrete `file:line` you have actually looked at is
  a guess: drop it or verify it first.

## Inputs

1. **Your plan**: `docs/.backend-checks/plan-<id>.json`. Read it first. `<CORE>` in every command
   below means the plan's `core_dir`. Key fields:
   - `mode`: `full` (analyze everything) or `incremental`.
   - `files_to_analyze`: the only files whose findings you produce this run, except in rerun sections.
   - `rerun_sections`: sections to evaluate across the **whole** scope. In incremental mode earlier
     findings of these sections are discarded, so re-report everything that still applies there. Use
     `section_hotspots` to find the relevant files.
   - `hotspots`: `{category: {file: [line, ...]}}` pointing at lines worth checking first.
   - `extra_hotspots`: hints inside the extra paths.
   - `stack`, `runtime`, `tests`: what was detected.
   - Sections **not** in `rerun_sections` keep their earlier findings for files you don't analyze. Only
     report findings located in `files_to_analyze` for those sections.
2. **The code.** If the orchestrator already loaded the bundle parts into your context (you are a fork),
   use them and don't read those files again. Otherwise run
   `python "<CORE>/scripts/bundle.py" --root . --plans docs/.backend-checks/plan-<id>.json` and Read every
   part it lists in one message (parallel Read calls). Bundle lines look like `   42| code`, where the
   number is the real line number in that file.
3. **Script outputs** named in your brief (e.g. `deps.json`, `dupes.json`). They're candidates: confirm
   each against the code before reporting it.

## Output: `findings-<id>.new.json`

```json
{
  "section_notes": {"3": "12 tests ran, 2 failed.", "7": "Not applicable (no upload handlers found)."},
  "findings": [
    {
      "section": "2a",
      "rule": "sql-injection",
      "severity": "Critical",
      "title": "SQL injection in menu search",
      "file": "api/src/routes/menu.js",
      "line": 8,
      "symbol": "GET /menu/search",
      "locations": ["api/src/routes/menu.js:9"],
      "related_files": ["api/src/db.js"],
      "problem": "The `q` query parameter is placed straight into the SQL string, so `' OR 1=1 --` returns every row.",
      "fix": "In api/src/routes/menu.js:8 use a placeholder (`WHERE name ILIKE $1`) and pass `[`%${q}%`]` as the parameter array.",
      "owasp": "A03 Injection"
    }
  ]
}
```

| Field | Rules |
|---|---|
| `section` | One of your brief's section ids, exactly (`"2a"`, `"10"`). |
| `rule` | A short kebab-case slug for the kind of problem (`sql-injection`, `idor`, `missing-rate-limit`). Use the same slug every run for the same kind of problem: together with file and symbol it identifies the finding across runs, so the user's answers stick. |
| `severity` (security) | `Critical` / `High` / `Medium` / `Low` (see your brief). |
| `impact` + `effort` (code quality) | `High`/`Medium`/`Low` and `S`/`M`/`L`. |
| `title` | Under 10 words, names the problem, not the fix. |
| `file`, `line` | Repo-relative path (as in the plan) and the 1-based line where the problem is. `line` may be `null` for file-level findings (e.g. a lockfile). |
| `symbol` | Enclosing route/function/class, e.g. `POST /orders/:id/pay` or `PaymentService.charge`. Stable across edits, so always fill it when there is one. |
| `locations` | Other places with the same problem, as `path:line` or `path:start-end`. One finding per problem, not one per occurrence. |
| `related_files` | Files whose change could fix or change this finding (the middleware it lacks, the shared helper). They trigger a re-check next run. |
| `problem` | 1–3 plain sentences: what is wrong and what an attacker/user/developer would hit. |
| `fix` | **One-line change** → one sentence naming the line and the change. **Bigger change** → explain what to change and how, in prose, or as a list of steps (`["step 1", "step 2"]`). No code blocks over ~5 lines. Prefer the smallest fix that fully solves it. |
| `needs_confirmation` + `question` | Only where your brief says so (e.g. security 4a): `true` plus one yes/no-style question the user can answer. |
| `section_notes` | Optional sentence per section, e.g. test results, `Not applicable (no uploads found)`, or `Could not check: deps.json had no network`. Give `""` to clear an old note. |
| `group` (code quality) | Optional short name shared by findings that should be refactored together (roadmap). |

Then run `python "<CORE>/scripts/findings.py" validate --root . --check <id>` and fix every error it
lists. Warnings about paths deserve a look too.

## What you return

Only this, under 15 lines. The orchestrator never needs the findings text from you:

```
<id>: <N> findings (Critical 2, High 5, Medium 4, Low 1) | questions: 1 | tests: 3 ran, 2 failed | notes: <anything the user must know, e.g. OSV unreachable>
```
