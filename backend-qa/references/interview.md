# Intent interview (Phase 4)

Purpose: turn every non-obvious behavior into a written decision the tests can assert. You never
decide intent yourself; you only propose options and record what the user picks.

## Question format (every question)

- AskUserQuestion, up to **4 questions per call**, 2–4 options each. The tool adds an "Other" box
  automatically: that is where the user writes an intent you didn't offer. Never add your own
  "Other" option, and never ask an open text question and wait.
- `header` ≤ 12 characters: the function or topic (`Login lock`, `Div by 0`, `Order del`).
- The question names the function and the situation concretely:
  "`calculateSplit(total, people)` — what should happen when `people` is 0?"
- **Recommended option first**, labelled "(Recommended)": the safest, most common industry
  behavior, not what the code happens to do.
- Each option's `description` says the observable result a test can check (status code, error
  code, returned value, DB state, email sent) and, when relevant, **"code now: …"** so the user
  sees where the code stands. If the code's current behavior is one of the options, mark it
  "(current code)" in the label; it's never auto-recommended for being current.
- Numbers get concrete options: *5 attempts / 15 min (Recommended)* / *10 attempts / 1 hour* /
  *3 attempts / 24 hours*. The user types another pair in "Other".
- Use `multiSelect: true` only for "which of these apply" questions (admin powers, which fields
  are editable), never for exclusive choices.
- Use a `preview` when comparing response shapes or a small table helps; keep it short.

If the user picks an option with a free-text note, record the note verbatim in the decision.
If the "Other" text is ambiguous, ask one follow-up with options built from their text.

## Order

1. **Global rules** (`G-n`), one round, only what the code doesn't settle consistently:
   validation error status (400 vs 422) and body shape, unauthenticated (401), forbidden role
   (403), someone else's resource (404 vs 403), unknown route, rate-limit status (429 + headers?),
   pagination default/max, soft vs hard delete default, time zone for dates, money representation
   (integer cents vs decimal), what unknown/extra body fields do (ignore vs reject).
2. **Access matrix** (`S-n`, see `scoping.md`).
3. **Modules**, high-risk first (auth, payments, permissions, deletion, uploads, webhooks), then
   medium, then low.

## Module rounds

Start each module with one question:

> **orders** — 6 functions, about 14 decisions (create, cancel, refund, list…). How should I handle it?
> - *Ask me each decision (Recommended)* — for high-risk modules
> - *Use recommended defaults and show me the list* — recommended for low-risk modules
> - *Skip testing this module*

- **Ask each:** go through the module's decisions, 4 per call. Group related ones in one call
  (all of `login`'s questions together).
- **Defaults:** write the recommended option for each decision, then show them in one message as
  a compact table (ID, situation, default) and ask *Accept these defaults (Recommended)* /
  *Let me change some*. "Change some" → ask which IDs (multiSelect, up to 4 per call; for more,
  "Other" with a list of IDs), then ask those individually. Accepted defaults are recorded with
  source `default`, which still means user-approved.
- **Skip:** record the module as skipped with the reason; its functions get `--skip`.

Never ask more than ~12 questions in a row without showing progress: "auth done (11 decisions);
next: orders (6 functions)".

## What makes a decision

One decision = one situation → one checkable expected result:

| ID | Situation | Expected | Source |
|---|---|---|---|
| F003-D2 | 5th failed login for the same account within 15 min | 429 `account_locked`; correct password also rejected until 15 min pass; lock email sent | user |

"Expected" must be specific enough to assert. "Handle gracefully" is not a decision; ask again
with concrete options.

`obvious` defaults (see `edge-cases.md` → "Never ask") are written without asking, with source
`obvious`, so the tests can still cite them. Show a one-line count of them per module ("+9 obvious
checks: auth required, bad input → 4xx, …") so nothing is hidden.

## Changed functions (rerun)

For each function with status `changed`:
1. `python "SKILL_DIR/scripts/map_functions.py" --root . --diff F012` prints the diff since the
   decisions were made.
2. Read the diff and the function's existing decisions. Build options from what actually changed:
   - *No, same intent (refactor only) (Recommended)* when the diff only renames/moves/restructures
   - *Yes: <specific change you see>* for each behavioral change visible in the diff
     ("max quantity check changed from 100 to 50", "now accepts a `coupon` field",
     "now soft-deletes instead of deleting")
   - *Yes, but differently from the code* — the user explains in "Other"; this often means the
     change is a bug.
3. Then, only for the parts that changed, ask the follow-up decisions (new inputs, new limits)
   the same way as new functions. Retire decisions that no longer apply (keep them in the
   **Retired** section with the date and reason) and keep the rest untouched.
4. `map_functions.py --accept F012` once its decisions are current.

Unchanged functions are never mentioned. New functions in an already-interviewed module get a
short round for just those functions.

## Recording

Write `qa/TEST_DECISIONS.md` after every AskUserQuestion answer (not at the end), so an
interrupted run loses nothing. Keep IDs stable forever: never renumber; new decisions get the next
number; retired IDs are never reused.
