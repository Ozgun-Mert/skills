# Plan and approval (Phase 4)

Write `DESIGN/plan.md` from `SKILL_DIR/templates/plan.md`. Show the user the **page plan** and the
**task table** (both as markdown tables in your reply), then ask for approval.

## Page plan: one row per route template

| Column | Content |
|---|---|
| Route | `/menu/[tableId]` (dynamic segments in brackets) |
| Page | Human name |
| Purpose | The one job of the page, from the user's point of view |
| Segment → style | `Catalog → Normal` |
| Data | Contract endpoints (`GET /api/menus/{id}`) or `mock: menus.json`; `static` when there's no backend; `local` for localStorage |
| Key components | `CategoryChips, ItemCard, ItemSheet, BasketBar` |
| States | Loading / empty / error / success: what each one shows, briefly |
| UX patterns | IDs from `ux-patterns.md` and `ux-principles.md` (e.g. `browse→cart`, L-Fitts, H1) |

Also cover the global pieces: layout shells (public header and footer, app sidebar), the 404 and error
pages, the toast system and the cookie banner (only when the site uses cookies that need consent).

## Task table: everything you'll do, in build order

| ID | Task | Files | Done when |
|---|---|---|---|
| T1 | Design tokens + fonts (light/dark) | `src/styles/tokens.css`, layout | tokens used, contrast pairs pass |
| T2 | API client + mock layer + fixtures | `src/lib/api/*`, `src/mocks/*` | every planned endpoint returns typed data in `mock` mode |
| T3 | Shared components | `src/components/ui/*` | each has hover/focus/active/disabled/loading |
| T4… | One task per page or per tightly linked group of pages | … | renders all four states; `ui_audit` has no blocker |
| Tn | FRONTEND.md (mock mode) | `FRONTEND.md` | lists every endpoint the UI calls |

Keep it to about 8–25 tasks. Each must be checkable. The front agent and the final check use this column.

## Stack line (new frontend only)

`Stack: SvelteKit + TypeScript + Tailwind v4 because 6 page types, mostly forms/lists, public pages need
SSR (references/build.md rubric).` Don't ask about it. It's here for information.

## Approval

```
question: "Here's the plan: <N> pages, <M> tasks. Start building?"
options:
  - "Start building (Recommended)": "I'll build it, then run the user/front review rounds until it's clean"
  - "Change something": "Tell me what to add, remove or restyle"
```

On "Change something", apply the change, show only the rows that changed, and ask again. After approval,
write `DESIGN/.work/routes.txt`: one concrete URL per page, with a real or mock id for dynamic routes
(`/menu/5`), and the 404 route with its expected status, `/this-page-does-not-exist [404]` (the scripts
treat a `[404]` suffix as the expected status, not as a failure). Then set `phase: "build"`.
