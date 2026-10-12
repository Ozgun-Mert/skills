# Review loop (Phase 6)

Two subagents, two personas, many rounds. The **user** sees only screenshots. The **front** sees only code
and the design system. You, the main agent, run the rounds and arbitrate. Subagents can't spawn
subagents, so every spawn happens from you.

## Setup (once)

1. Start the dev server with Bash `run_in_background: true` (e.g. `npm run dev -- --port 5173`). Wait
   until the URL answers (`curl -s -o /dev/null -w "%{http_code}" <url>`). Save `dev_url` and `dev_cmd` in
   `state.json`.
2. Check that `DESIGN/.work/routes.txt` is current with the plan.
3. In `backend_mode = mock`, make sure the empty and error mock switches work (`?mock=empty`,
   `?mock=error`), so round tasks can include "what happens when there's nothing yet?".

## Each round N

Folder: `DESIGN/.work/reviews/round-N/`.

### 1. Write `tasks.md`

- **Persona:** one or two lines built from the real target users in `DESIGN/project.md`: name, age,
  habits, which famous apps they use, device and hurry level. Rotate through personas and devices
  across rounds: phone first (most users), then desktop, then admin or staff roles, then edge
  cases (slow, careful, older user, keyboard only).
- **Tasks:** 3–6, **goal-only**. Say *what* the user wants, never *how* or *where*.
  - ✅ "You're at table 5. Order two lahmacun and an ayran, then pay."
  - ❌ "Click the Lahmacun card, press Add, open the basket from the bottom bar."
- Across the rounds, cover every main flow in `plan.md`. Include at least one task that hits an empty
  or error state (by going to `<route>?mock=empty`, or doing something that naturally fails, like a wrong
  password).
- From round 2 on, re-test the flows that had complaints, but with a fresh persona and with wording
  that doesn't hint at the old problem.

### 2. Run the user

Spawn a **new** Agent (subagent_type `general-purpose`, foreground) whose prompt is the part of
`persona-user.md` below the line, with `{{PERSONA}}`, `{{URL}}`, `{{DEVICE}}`, `{{WIDTH}}`,
`{{ROUND_DIR}}`, `{{ROUTES_FILE}}`, `{{SKILL_DIR}}` (absolute), `{{TASKS}}` and `{{N}}` filled in. It
must be fresh every round: a returning user isn't a first-time user.

When it returns, read `user-report.md`. Glance at 2–3 of the screenshots it cites, to make sure the
complaints are real and not artefacts of the script (e.g. a step clicked the wrong element because two
had the same name). Strike out artefacts in `decisions.md`, with the reason.

### 3. Run the front

Round 1: spawn an Agent (general-purpose, foreground) with `persona-front.md` filled in, and save the
agent ID it returns as `front_agent_id` in `state.json`. Later rounds: `SendMessage` to that ID with the
new round folder. When it returns, read
`front-report.md`.

### 4. Arbitrate

For each complaint marked `rejected` or `partial`:
- **Accept** when the reason is real: the user explicitly chose this style, it's a legal or content
  requirement, or it's the market convention per `ux-patterns.md`. Record it in
  `DESIGN/.work/reviews/decisions.md` (`round, complaint, decision, reason`).
- **Send back** when it isn't. SendMessage the front agent with your reasoning and wait for the fix.

If front suggests a `brand.md` change and you agree, update `brand.md`, note the change in `decisions.md`
and tell front.

### 5. Decide whether to stop

Stop when **both** are true:
- The latest user report has **no complaints** left after removing the artefacts and the accepted decisions,
  and visual appeal is ≥ 8 with wordiness = 3.
- Every task in `DESIGN/plan.md` is ticked.

Otherwise, start round N+1 with a new user persona. After round 6, and every 3 rounds after that, ask the
user:

```
question: "Round N done: <x> complaints left (<list of the top 3>). Keep going?"
options:
  - "Keep iterating (Recommended)": "Run more user/front rounds until no complaints"
  - "Stop here and finish": "Do the final check with the remaining complaints listed"
```

Recommend stopping instead when two rounds in a row produced only minor complaints that contradict each
other (user A wants X, user B wants not-X). That's taste, not defects.

Update `state.json` with `round`, `open_complaints` and the stop reason.

## Cost discipline

- The user persona shoots at 2 widths for looking and audits at 5. Don't ask it for more.
- The front fixes at the root (shared components and tokens), so later rounds get shorter.
- Never paste screenshots or whole reports into SendMessage. Send paths.
