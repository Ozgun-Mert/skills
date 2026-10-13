# Final check (Phase 7)

You run this yourself, after the review loop stops. Nothing here is delegated.

1. **Project checks:** run `build`, `lint`, `check` (typecheck) and `test` with the project's package
   manager. Any failure → fix it (frontend files only) and run again.
2. **Production build serves:** start the production preview (`npm run build && npm run preview` /
   `next start` / `node build`) in the background and use its URL for the next steps. This catches
   dev-only behaviour (hydration errors, missing env vars).
3. **Audit everything:**
   `python "SKILL_DIR/scripts/ui_audit.py" --url <url> --routes-file DESIGN/.work/routes.txt --out DESIGN/.work/final/audit --annotate --fail-on major`
   It must exit 0 with no `stuck-invisible` content. Then repeat:
   - with `--reduced-motion`. Every piece of content must still be visible, and no WebGL canvas may be
     animating (the Motion wrapper renders the final states).
   - with `--dark`, if the site supports dark mode.

   `webgl-mobile` hints at 360/390 mean a WebGL background wasn't swapped for its static fallback;
   fix them. If anything is major, fix it and rerun. List the minor issues in the report; leaving them is OK only if they are accepted in
   `decisions.md` or are clear false positives (say which).
4. **Final screenshots:**
   `python "SKILL_DIR/scripts/shoot.py" --url <url> --routes-file DESIGN/.work/routes.txt --out DESIGN/.work/final/shots`
   (exit code 0 = every route has its expected status). Open the 390 and 1280 shots of the main pages and
   look at them yourself.
5. **Main flows still work:** rerun the `steps.json` of the last round's tasks with `browse.py`. Each one
   must exit 0.
6. **Plan complete:** every task in `DESIGN/plan.md` is ticked. In mock mode, `FRONTEND.md` lists every
   function in the mock client, and switching `API_MODE` to `http` is documented. Make sure a missing
   API URL produces a clear console message, not a crash.
7. **No leftovers:**
   - search the source for `lorem`, `TODO: design`, `console.log` debugging lines and unused mock imports
     in `http` mode
   - list every `{{PLACEHOLDER: …}}`
8. Stop the background servers you started.

Then write the report described in SKILL.md Phase 7, and set `state.json` `phase: "done"`.
