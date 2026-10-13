# Plan: <project>  (approved <date>)

Stack: <framework + reason, or "existing: …">
Backend mode: <contract | mock | none> (API client: `src/lib/api/client.ts`)
Tokens: DESIGN/brand.md · Styles: DESIGN/styles.md · Kits: shadcn/ui + React Bits (SKILL_DIR/design/component-kits.md)

Key components use `ui:` for shadcn/ui and `RB:` for React Bits. Each Fancy page lists 8 or more `RB:` pieces (its motion budget).

## Page plan
| Route | Page | Purpose | Segment → style | Data | Key components | States (loading / empty / error / success) | UX patterns |
|---|---|---|---|---|---|---|---|
| / | Home | … | Landing → Fancy | static | Hero, … | – / – / – / ✓ | L-VonRestorff, … |

Global: layout shells, 404 (`/this-page-does-not-exist [404]`), error page, toasts, <cookie banner if needed>.

## Task table
| ✓ | ID | Task | Files | Done when |
|---|---|---|---|---|
| [ ] | T1 | shadcn init + brand tokens → shadcn variables + fonts (light/dark) | globals.css, lib/tokens.ts | tokens used; contrast pairs pass |
| [ ] | T2 | API client + mock layer | src/lib/api/*, src/mocks/* | every planned endpoint returns typed data |
| [ ] | T3 | shadcn components + React Bits pieces + Motion wrapper | components/ui/*, components/motion/* | themed from tokens; all states; reduced motion → final state |

## Review rounds
| Round | Persona / device | Complaints (B/M/m) | Fixed | Appeal | Notes |
|---|---|---|---|---|---|
