# Build (Phase 5)

Build the approved plan in task order and tick each task in `DESIGN/plan.md` when its "Done when" is
true. You write this first version yourself. The front agent polishes it in the review loop.

## 1. Stack

The UI is built from **shadcn/ui** and **React Bits** (`SKILL_DIR/design/component-kits.md`). Both are
React kits, so new frontends are React.

**Existing frontend:** keep its framework, router and styling, and never migrate.
- React (Next.js, Vite, Remix/React Router, Astro + React): add shadcn/ui (`npx shadcn@latest init`) and
  React Bits in place. If it already has another component library, keep it for existing screens and use
  shadcn for new ones only when the two can share the tokens.
- Vue/Nuxt: shadcn-vue + Vue Bits. Svelte/SvelteKit: shadcn-svelte, with the React Bits effects rebuilt
  (`component-kits.md` §8).

**No frontend yet:** decide with this rubric and don't ask the user.

| Situation | Stack |
|---|---|
| Any public pages (landing, catalog, blog) or an app with public parts | **Next.js** App Router + TypeScript (`shadcn init -t next`) |
| Mostly content/marketing (landing, blog, docs) with few interactive parts | **Astro** + React islands (`shadcn init -t astro`) |
| Internal tool behind login, no public pages | **Vite + React + TypeScript** (`shadcn init -t vite`) |

Defaults for all of them:
- Tailwind CSS v4, with shadcn's CSS variables set from `brand.md` (`component-kits.md` §2).
- shadcn/ui for every primitive (button, field, dialog, sheet, table, sidebar, sonner…); React Bits for
  motion, in the amount the segment's style asks for (`component-kits.md`: Fancy = lots, Playful = many
  micro-interactions, Normal = light, Strict = none).
- Zod for form validation (with shadcn `field`); Lucide icons (shadcn's default) or the set in `brand.md`.
- GSAP and `motion` come in through the React Bits components that need them. Add Lenis only for a Fancy
  segment that needs smooth scrolling, and only once.
- Package manager: the one whose lockfile is in the repo, otherwise `npm`.
- Scripts named `dev`, `build`, `lint`, `check` (typecheck) and `test`.

Place the frontend in the repo root when it's frontend-only. Otherwise use `frontend/` next to `backend/`.

## 2. Tokens and global styles (T1)

- Run `shadcn init` for the stack, then put every token from `brand.md` into `globals.css`. This means
  shadcn's variables (`--background`, `--primary`, `--muted-foreground`, `--ring`, `--radius`,
  `--chart-*`…, mapped as in `component-kits.md` §2) for `:root` and `.dark`, plus the brand's extra
  tokens (type scale, spacing, shadows, motion durations and easing). Mirror the colors in
  `lib/tokens.ts` so React Bits props can use them.
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

Add the shadcn/ui components and blocks the plan names, then adjust them once to the tokens. Copied source
is yours to edit. Cover at least:
- button (variants plus a loading state), field, input, textarea, select, checkbox, radio-group, switch
- card, badge, avatar, dialog, sheet, dropdown-menu, tabs, sonner, tooltip
- table (plus the data-table recipe, with a mobile card mode), pagination, skeleton, empty, breadcrumb
- sidebar / navigation-menu for the shells, plus the blocks that fit (`dashboard-01`, `login-0x`)

Add the React Bits components the plan names for each page (`npx shadcn@latest add @react-bits/<Name>-TS-TW`,
into `components/motion/`). Recolor them from the tokens, and wrap them with the shared reduced-motion helper
(`components/motion/Motion.tsx`). Follow every rule in `component-kits.md` §3: nothing stuck invisible, one
WebGL canvas in view, static fallbacks on mobile, `'use client'` leaves.

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
- Fancy segments: follow `fancy.md` and the **Fancy recipes in `component-kits.md` §4**. Every section
  animates in; the hero has an animated headline, a background and a CTA micro-interaction; at least 8 React
  Bits pieces per page, colored from the tokens. Lazy-load WebGL and keep the reduced-motion and mobile
  fallbacks.
- Playful segments: `playful.md` + `component-kits.md` §5 (micro-interactions on every control and
  feedback moment). Normal segments: shadcn plus light motion (§6). Strict segments: no motion (§7).

## 6. FRONTEND.md (mock mode)

Fill `SKILL_DIR/templates/FRONTEND.md` from `mock.ts`: base URL and env var, auth, error format, and one
section per endpoint with its request, its response and the page that uses it. Put it at the project
root, or next to the existing docs. It is the contract handed to the backend developer.

## 7. Before the review loop

- `dev` runs with no errors in the terminal or the browser console.
- `build`, `lint` and `check` pass, or the failures are listed and fixed now.
- `python "SKILL_DIR/scripts/ui_audit.py" --url <dev-url> --routes-file DESIGN/.work/routes.txt --out DESIGN/.work/pre-review --fail-on blocker`
  exits 0, and it reports no `stuck-invisible` content (an entrance animation that never fires). Fix the majors it reports that are clearly real, so the user persona spends its attention on
  things only a human eye catches.
