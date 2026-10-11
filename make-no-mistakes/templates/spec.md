# <Product name>: spec

> Single source of truth for every worker. Written by the orchestrator in Phase 3, from
> `mnm/research.md` and `mnm/decisions.md`. Only the orchestrator edits it.

## 1. Summary
- **What:** <one sentence>
- **For whom:** <audience>
- **Scope:** full | MVP (<what is deferred>)
- **UI language(s):** <…> · **Content language(s):** <…>
- **Style:** Professional | Balanced | Fun
- **Compliance:** <GDPR/KVKK/none>

## 2. Stack (decided by the orchestrator, see decisions.md for the reason)
- Backend: <FastAPI | Bun+TS (Hono, Drizzle) | Go (chi, sqlc)> · DB: PostgreSQL 16 (+RLS)
- Frontend: <SvelteKit | Next.js App Router> · Tailwind v4 · Playwright
- Auth: server-side sessions (HttpOnly cookie), argon2id<, Google OAuth>
- Dev: docker-compose (postgres<, mailpit>), `.env.example`

## 3. Roles
| Role | Who | Can |
|---|---|---|

## 4. Features and acceptance criteria
### F1 <feature> (<"as competitors" | tweak: …>)
- F1.1 <testable criterion>
- F1.2 …

### U1 <user-added feature>
- …

## 5. Data model
| Table | Fields (type, constraints) | Owner column | Indexes | RLS policy |
|---|---|---|---|---|
| users | id uuid pk, email citext unique, password_hash text, created_at | — | email | self only |

## 6. Access-control matrix
(Format and rules: the skill's `references/security.md` §1. Every endpoint maps to a row.)

| Resource | Action | Owner | Shared member | Other user | Other tenant's admin | Anonymous | Admin | Ownership rule |
|---|---|---|---|---|---|---|---|---|

## 7. API
Contract: `mnm/contracts/openapi.yaml`. Conventions:
- JSON, `/api/v1` prefix
- errors `{ "error": { "code", "message", "request_id" } }`
- cursor pagination `?cursor=&limit=` (max 100)
- timestamps ISO-8601 UTC

## 8. Pages
| Path | Page type | Public? | Search intent / primary keyword | Data | Notes |
|---|---|---|---|---|---|
| / | Landing | yes | <commercial keyword> | static | |
| /app | Dashboard | no (noindex) | — | GET /me, … | |

## 9. Design tokens
```css
:root {
  --color-bg: …; --color-fg: …; --color-muted: …; --color-brand: …; --color-brand-fg: …;
  --color-accent: …; --color-danger: …; --color-success: …; --color-border: …;
  --radius: …; --shadow-1: …; --font-sans: …; --font-display: …;
  --step-0: 1rem; --ratio: …; --motion-fast: …;
}
@media (prefers-color-scheme: dark) { :root { … } }
```

## 10. Non-functional targets
- LCP < 2.5s, CLS < 0.1, INP < 200ms on mobile for public pages
- API p95 < 300ms for normal reads at the expected scale
- WCAG 2.2 AA
- Zero Critical/High security findings; isolation matrix 100% pass

## 11. Placeholders (facts the user must still supply)
| Placeholder | Where | Needed from user |
|---|---|---|
