# Plan: <project>  (approved <date>)

Stack: <framework + reason, or "existing: …">
Backend mode: <contract | mock | none> (API client: `src/lib/api/client.ts`)
Tokens: DESIGN/brand.md · Styles: DESIGN/styles.md

## Page plan
| Route | Page | Purpose | Segment → style | Data | Key components | States (loading / empty / error / success) | UX patterns |
|---|---|---|---|---|---|---|---|
| / | Home | … | Landing → Fancy | static | Hero, … | – / – / – / ✓ | L-VonRestorff, … |

Global: layout shells, 404 (`/this-page-does-not-exist [404]`), error page, toasts, <cookie banner if needed>.

## Task table
| ✓ | ID | Task | Files | Done when |
|---|---|---|---|---|
| [ ] | T1 | Design tokens + fonts (light/dark) | src/styles/tokens.css | tokens used; contrast pairs pass |
| [ ] | T2 | API client + mock layer | src/lib/api/*, src/mocks/* | every planned endpoint returns typed data |
| [ ] | T3 | Shared components | src/components/ui/* | all states (hover/focus/active/disabled/loading) |

## Review rounds
| Round | Persona / device | Complaints (B/M/m) | Fixed | Appeal | Notes |
|---|---|---|---|---|---|
