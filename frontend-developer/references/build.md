# Build (Phase 5)

Build the approved plan in task order and tick each task in `DESIGN/plan.md` when its "Done when" is
true. You write this first version yourself. The front agent polishes it in the review loop.

## 1. Stack

**Existing frontend:** keep its framework, router, styling and component library. Add only what is
missing, and prefer libraries already in the project.

**No frontend yet:** decide with this rubric and don't ask the user.

| Situation | Stack |
|---|---|
| Public pages that need SEO and ≤ 8 page types, mostly lists/forms | **SvelteKit** (Svelte 5) + TypeScript |
| > 8 page types, or app-like (dashboards, editors, nested layouts) | **Next.js** App Router + TypeScript |
| Mostly content/marketing (landing, blog, docs) with a few interactive islands | **Astro** + islands (React or Svelte) |
| Internal tool behind login, no public pages | **Vite + React + TypeScript** (or SvelteKit with SSR off) |

Defaults for all of them:
- Tailwind CSS v4 reading the CSS variables from `brand.md` (`@theme`).
- Zod for form validation.
- Lucide icons (or the icon set in `brand.md`).
- For Fancy segments: GSAP + ScrollTrigger and Lenis, loaded only on those routes. Three.js/OGL
  only if `brand.md` calls for a 3D moment.
- Package manager: the one whose lockfile is in the repo, otherwise `npm`.
- Scripts named `dev`, `build`, `lint`, `check` (typecheck) and `test`.

Place the frontend in the repo root when it's frontend-only. Otherwise use `frontend/` next to `backend/`.

## 2. Tokens and global styles (T1)

- CSS custom properties for every token in `brand.md`: colors (light plus a `[data-theme=dark]` /
  `prefers-color-scheme` block), font families, type scale, spacing, radius, shadows, motion.
  Segment overrides for Fancy and Playful apply under a `data-style="fancy"` attribute on the segment's
  layout.
- Self-hosted fonts (`@fontsource/*`, `next/font` or `font-display: swap` files), and preload the display
  font.
- Base layer:
  - `box-sizing`
  - `img { max-width: 100%; height: auto }`
  - `overflow-wrap: anywhere` on long text containers
  - `:focus-visible` ring using `--focus`
  - `cursor: pointer` on `button, [role=button], summary, label[for], a`
  - `@media (prefers-reduced-motion: reduce)` disables transitions and animations
- `<meta name="viewport" content="width=device-width, initial-scale=1">` and `<html lang>`.

## 3. Data layer (T2)

One API client module. Pages and components call **only** the client, never `fetch` directly.

```
src/lib/api/
  client.ts        // export const api = API_MODE === 'mock' ? mockApi : httpApi
  http.ts          // base URL from env (VITE_API_URL / NEXT_PUBLIC_API_URL / PUBLIC_API_URL), auth header or cookies,
                   // JSON, typed errors {status, code, message, fieldErrors?}, timeout, AbortController
  mock.ts          // same function signatures; reads src/mocks/*.json; 300–800 ms random latency;
                   // keeps writes in memory (or localStorage) so flows work end to end
  types.ts         // request/response types from the contract (or openapi-typescript when there's a spec)
src/mocks/*.json   // realistic fixtures in the UI language; clearly mock (no real people or brands)
```

Mock images must show the actual thing: a photo of *that* dish or product from a free-licence source
(Wikimedia Commons, Unsplash) with the licence noted in the fixture, or a neutral illustrated
placeholder. Random placeholder photos (picsum and the like) were the first thing test users
distrusted ("horses for a pide").

- `backend_mode = contract`: `API_MODE` defaults to `http`. Mocks are optional; add them only to develop
  states the backend can't produce easily.
- `backend_mode = mock`: `API_MODE` defaults to `mock`. Every function in `mock.ts` is listed in
  `FRONTEND.md` with the exact shapes, so the backend developer can implement it.
- `backend_mode = none`: there is no client. Content lives in `src/content/*` and persistent UI state in a
  small `store` module.
- Mock mode must also be able to show **empty and error states**. Support `?mock=empty` and
  `?mock=error` (or a dev-only toggle) so the user persona and the audit can see them.
- Realtime from the contract (WebSocket/SSE) goes behind the client too. The mock emits events on timers.

## 4. Components (T3)

Build the shared set once from the tokens and reuse it everywhere:
- button (primary, secondary, ghost, danger; sizes; loading state)
- input, textarea, select, checkbox, radio, switch (all with label, hint and error)
- card, badge, avatar, dialog/sheet, dropdown menu, tabs, toast, tooltip
- table (with a mobile card mode), pagination, skeleton, empty state, error state, breadcrumb
- layout shells

Every interactive component has hover, focus-visible, active, disabled and loading states.

Watch these rules here (they are the user persona's favourite complaints, see `ux-principles.md` D):
- Buttons in a row share a height and never wrap unevenly. Use short labels, `white-space: nowrap`, and
  stack the row vertically below a breakpoint instead of letting one label wrap.
- Cards in a grid row have equal heights (`grid` + `align-items: stretch`, with the content inside
  using `flex-col` and `mt-auto` footers).
- Every clickable element is a `<button>` or `<a>`. Never put `onClick` on a `<div>`.
- Touch targets are ≥ 44px on mobile.

## 5. Pages (T4…)

For each page, follow its segment's style file and `DESIGN/ux-patterns.md`:
- Exactly one `<h1>`, a logical heading order, landmark elements, a unique `<title>` and meta description.
- Four states for every data view: loading (a skeleton shaped like the content), empty (explanation +
  CTA), error (human message + retry), success.
- Forms:
  - a label on every field; required *and* optional fields marked
  - inline errors on blur and on submit; server field errors mapped back to their fields
  - input never lost on error; a submit button with a spinner that is disabled while pending
- Destructive actions use undo toasts or confirm dialogs that name the object.
- Responsive from 360px. Check 360, 390, 768, 1280 and 1440.
- Copy: short, specific, in the project's language. Missing facts use `{{PLACEHOLDER: name}}`.
- Fancy segments: follow `fancy.md` with its non-negotiables. Lazy-load motion libraries and WebGL,
  and keep the reduced-motion fallback.

## 6. FRONTEND.md (mock mode)

Fill `SKILL_DIR/templates/FRONTEND.md` from `mock.ts`: base URL and env var, auth, error format, and one
section per endpoint with its request, its response and the page that uses it. Put it at the project
root, or next to the existing docs. It is the contract handed to the backend developer.

## 7. Before the review loop

- `dev` runs with no errors in the terminal or the browser console.
- `build`, `lint` and `check` pass, or the failures are listed and fixed now.
- `python "SKILL_DIR/scripts/ui_audit.py" --url <dev-url> --routes-file DESIGN/.work/routes.txt --out DESIGN/.work/pre-review --fail-on blocker`
  exits 0. Fix the majors it reports that are clearly real, so the user persona spends its attention on
  things only a human eye catches.
