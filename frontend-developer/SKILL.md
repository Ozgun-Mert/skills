---
name: develop-frontend
description: Builds a project's frontend with award-level UI/UX. Reads what the project is (PROJECT.md, or any .md/.txt that describes it) and how to talk to the backend (FRONTEND.md, a link, or any API doc it finds); if there is no backend contract it asks Yes / No / Not implemented and, for not implemented, builds against a mock data layer behind the same API client. Researches similar sites (global and local, e.g. Wolt + Yemeksepeti for a Turkish food app) and their UX patterns, saves it all in a gitignored DESIGN/ folder so it never researches twice, asks which style each part should have (Fancy / Normal / Strict / Playful per segment: landing, panels, blog…), builds the UI from shadcn/ui components and React Bits animations (Fancy segments get lots of motion: animated headlines, WebGL backgrounds, scroll reveals, interactive cards; Normal stays light; Strict stays still), shows a page plan and task table for approval, builds, then runs a review loop where a "user" subagent that has never seen the site completes tasks through Playwright screenshots and reports what looks broken, confusing, wordy or ugly, and a "front" subagent fixes it, until the user has no complaints. Use whenever the user types /develop-frontend (with or without a FRONTEND.md path or URL), or asks to build, design, redesign or polish a website/web app frontend, UI or UX, make it look premium, animated or award-winning, use shadcn/ui or React Bits, or connect a UI to an existing backend API.
argument-hint: "[FRONTEND.md path or URL] [what the project is]"
---

# /develop-frontend

Input: `$ARGUMENTS` can hold, in any order, a path or URL to the backend contract (FRONTEND.md or similar), a
path to the project description, and/or a plain-text description of the project. All of them are optional.

`SKILL_DIR` = the "Base directory for this skill" shown when this skill loaded. Scripts are run as
`python "SKILL_DIR/scripts/<name>.py"`. `find_docs.py` and `ensure_gitignore.py` use the standard library only.
`shoot.py`, `browse.py` and `ui_audit.py` need Playwright. The baseline design knowledge is in
`SKILL_DIR/design/`: `fancy.md`, `normal.md`, `strict.md`, `playful.md`, `ux-principles.md` and
`component-kits.md`, which covers shadcn/ui + React Bits: install, theming, motion rules and recipes for each style. Read each
reference file when you reach the phase that points to it, not all up front.

You are the **main agent**. You discover the context, research, interview, plan, build the first version, run
the review loop between two subagents and do the final check.

## Hard rules

1. **DESIGN/ is always gitignored.** Phase 0 runs `ensure_gitignore.py` before anything is written to
   `DESIGN/`, in every project, every time.
2. **Never touch backend code or git.** You change frontend files only. Read-only git commands
   (`git status`, `git ls-files`) are fine. If a page needs data the contract doesn't offer, add it to
   `FRONTEND.md` under "Requested by the frontend" and use mock data for it.
3. **Options, not essays.** Ask every question with AskUserQuestion, 2–4 options, the recommended option first
   and labelled "(Recommended)". Never ask about architecture (framework, libraries, folders); you decide those
   with `references/build.md`. Ask about the product and the look.
4. **Research once.** If `DESIGN/` already holds research for this project, reuse it. Re-research only when the
   user asks for it or the project's domain has changed.
5. **Be original.** Take patterns from competitors, never their branding, copy, logos or exact palettes. Fonts
   and colors are chosen for this project's topic and must differ from the main competitors.
6. **Never fabricate.** No fake reviews, stats, prices, company facts or testimonials. Use a visible
   `{{PLACEHOLDER: name}}` instead. Mock data looks realistic, lives only in the mock layer and is labelled
   as mock.
7. **Talk in the user's language.** Write code and DESIGN files in English. UI copy uses the project's language(s).
8. **On Windows Git Bash**, a route argument that starts with `/` gets rewritten to `C:/Program Files/Git/...`.
   The scripts undo this, but `--routes-file` is the safest way to pass routes.

## Phase 0: Preflight

1. `python "SKILL_DIR/scripts/ensure_gitignore.py" --root .` adds `/DESIGN/` to `.gitignore`. If it reports
   `tracked_files`, tell the user to run `git rm -r --cached DESIGN` themselves.
2. `python -c "import playwright"`. If that fails, show the user
   `python -m pip install playwright` and `python -m playwright install chromium` and ask to run them
   (AskUserQuestion: "Install now (Recommended)" / "I'll do it myself"). The review loop can't run without
   Playwright, but Phases 1–5 can.
3. **Resume.** If `DESIGN/.work/state.json` exists, continue from its `phase` and never re-ask what
   `DESIGN/` already records. Otherwise create it with `{"phase": "context"}`. Update `phase` at the end of
   every phase.

## Phase 1: Context (read `references/context-discovery.md`)

You need two things before anything else: **what the project is** and **where its data comes from**.

1. **Project folder.** The current directory is the project. If it is empty or not a project, and
   `$ARGUMENTS` doesn't describe one, ask the user for the project folder path or a text description, and
   **wait**.
2. Run `python "SKILL_DIR/scripts/find_docs.py" --root .` once. It ranks every .md/.txt file as a project
   description and as a backend contract.
3. **PROJECT.md:** take it from the arguments, then from `PROJECT.md`, then from the top `project`
   candidates. Read them and judge whether they really describe the product: what it does, for whom, its main
   features. A setup-only README doesn't count. Nothing fits → ask for a description and wait. Write the
   result, or a pointer to it, to `DESIGN/project.md`.
4. **FRONTEND.md:** take it from the arguments (a path, or a URL fetched with WebFetch), then from
   `FRONTEND.md`, then from the top `backend` candidates. Also look for `openapi.*`/`swagger.*` files and
   the backend's route files, reading them only. If you find nothing, ask:
   **"Does this project have a backend the frontend should talk to?"**
   - **Yes:** wait until the user gives a file, a link or a text. Then use it.
   - **No:** the project is standalone, so there is no data layer. Content is static or kept locally.
   - **Not implemented:** the backend will exist but doesn't yet. Write `FRONTEND.md` from
     `SKILL_DIR/templates/FRONTEND.md`, listing every endpoint the UI needs. Build the UI against a mock
     layer behind the same client.
5. Record in `state.json`: `project_doc`, `backend_mode` (`contract` / `none` / `mock`), `contract_doc`, the
   detected frontend stack (if any) and the language(s) and market.

**From here on, all data "comes from the backend".** Pages call one API client and never know whether it is
real or mock. Switching to the real backend later is a one-line change of `API_MODE`.

## Phase 2: Research (read `references/project-research.md`), skipped if already in DESIGN/

1. Send 4–6 WebSearch calls **in one message**, in English and in the project's local language/market, to
   find similar products. Fetch the 3–6 most relevant sites; screenshots of them help
   (`shoot.py --url https://competitor.com --routes / --widths 390,1280 --viewport-only`).
   Example: a Turkish QR menu ordering app → Wolt, Yemeksepeti, Getir Yemek, Trendyol Yemek, Uber Eats,
   DoorDash, plus QR menu products (e.g. FineDine, Menulux).
2. Write these files to `DESIGN/` (formats are in the reference):
   - `similar-sites.md`: competitors and how they do layout, navigation, density, type and color.
   - `ux-patterns.md`: each user flow, the pattern competitors use for it, and where we apply it.
   - `normal-polished.md`: `SKILL_DIR/design/normal.md` refined for this domain and audience.
   - `brand.md`: our own fonts and palette (with reasons, contrast ratios and how they differ from
     competitors), plus a type scale, radius, shadow and motion tokens.
   - `README.md`: an index of the DESIGN files and of which baseline files from `SKILL_DIR/design/` apply.

## Phase 3: Style interview (read `references/interview.md`)

1. Split the planned UI into **segments**: landing/marketing, auth, panels/dashboard, lists/catalog,
   detail, forms/checkout, blog/content, docs/help, settings/account, admin. Keep only the ones this project has.
2. Ask one question per segment, 4 per AskUserQuestion call. The options are **Fancy / Normal / Strict /
   Playful**, with the recommendation for this segment first. Each option's description says in one line
   what it means for this segment.
3. Optionally ask one more question about the overall mood, with options from `brand.md`. The user can always
   type their own answer.
4. Save the answers to `DESIGN/styles.md`: segment → style → the design file to follow, plus any notes.

## Phase 4: Plan and approval (read `references/plan-format.md`)

Write `DESIGN/plan.md` from `SKILL_DIR/templates/plan.md`:
- **Page plan:** route, purpose, segment → style, data (endpoint or mock), key components, and the four
  states.
- **Task table:** everything you will do, in order. Each row has an ID, the task, the files it touches and a
  done check.
- **Stack** (if you chose it) with a one-line reason, and the shared tokens and components.

Show both tables to the user, then ask: "Start building (Recommended)" / "Change something". Loop until they
approve. Write `DESIGN/.work/routes.txt` (one route per line, with a sample id for dynamic routes).

## Phase 5: Build (read `references/build.md`)

Build the whole plan yourself, on **shadcn/ui + React Bits** (`SKILL_DIR/design/component-kits.md`). A new
frontend is React: Next.js, Astro + React or Vite + React.
1. `shadcn init`, then put the tokens from `brand.md` into shadcn's CSS variables, including dark mode.
2. The shadcn components and blocks the plan needs, plus the React Bits pieces
   (`npx shadcn@latest add @react-bits/<Name>-TS-TW`), recolored from the tokens and wrapped for
   reduced motion.
3. The API client (`real` or `mock`).
4. The pages, segment by segment. Each segment follows its style file, its recipe in
   `component-kits.md`, `ux-principles.md` and `DESIGN/ux-patterns.md`.
   - **Fancy pages get lots of motion:** an animated headline, a living background, a CTA effect,
     every section animating in, and 8 or more React Bits pieces in all.
   - Playful pages get micro-interactions.
   - Normal pages get light entrances.
   - Strict pages get none.

Every async view has loading, empty, error and success states. Mark tasks done in `plan.md` as you go.
Before the review loop starts, the dev server must run with no errors, and `ui_audit.py --fail-on blocker`
must pass with no `stuck-invisible` content.

## Phase 6: Review loop: user ⇄ front (read `references/review-loop.md`)

1. Start the dev server in the background and note its URL in `state.json`.
2. Write `DESIGN/.work/reviews/round-N/tasks.md`: a short persona drawn from the project's real users, plus
   3–6 **goal-only** tasks with no UI hints, e.g. "You're at table 5. Order two lahmacun and one ayran, and
   pay." Cover every main flow over the rounds. Personas and devices rotate (phone in one round, desktop in
   the next; customer, then admin).
3. **User subagent.** Spawn a **fresh** Agent (`general-purpose`, foreground) whose prompt is
   `references/persona-user.md` with the URL, the round folder, `SKILL_DIR` and tasks.md filled in. It sees
   the site only through `shoot.py`, `browse.py` and `ui_audit.py` screenshots, never source code or
   DESIGN files. It writes `round-N/user-report.md`.
4. **Front subagent.** In round 1, spawn an Agent (`general-purpose`, foreground) with
   `references/persona-front.md` filled in, and save the agent ID it returns as `front_agent_id` in
   `state.json`. In later rounds, continue that agent with SendMessage (`to: <front_agent_id>`), so it
   keeps its code context. If that fails, spawn a fresh one with the previous `front-report.md` paths. The front agent fixes every complaint, finishes any open plan tasks, runs
   build, lint and typecheck, and writes `round-N/front-report.md`.
5. **You arbitrate.** Read both reports. When front rejects a complaint, you decide whether the rejection is
   valid (for example, the user chose that style) or invalid (send it back). Record each decision in
   `DESIGN/.work/reviews/decisions.md`.
6. Repeat with round N+1 and a **new** user subagent, which knows nothing about the site.
   **Stop when** a round's user report has no complaints left (after removing the ones accepted in
   `decisions.md`) **and** every task in `plan.md` is done. After round 6, and every 3 rounds after that,
   ask the user: "Keep iterating (Recommended)" / "Stop here and finish".

## Phase 7: Final check (read `references/final-check.md`)

1. The project's build, lint, typecheck and tests pass.
2. `ui_audit.py --routes-file DESIGN/.work/routes.txt --fail-on major` exits 0 at every width: in light mode,
   in dark mode (if supported) and with `--reduced-motion`. No content may be stuck invisible, and no WebGL
   background may remain on phone widths.
3. There are no console errors, every route returns 200 and every plan task is done.
4. `shoot.py` produces a final screenshot set in `DESIGN/.work/final/`.

Set `phase: "done"`. Report to the user in their language:
- what was built, the stack and the style of each segment, with the main shadcn/React Bits pieces on
  each Fancy page (React Bits is MIT + Commons Clause: free to use in the product, not to resell)
- how many review rounds ran and the biggest fixes
- the final audit counts
- the open `{{PLACEHOLDER}}`s
- `backend_mode`, and in mock mode which `FRONTEND.md` endpoints the backend must implement and how to switch
  to the real backend
- how to run the app
