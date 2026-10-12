# Context discovery (Phase 1)

Goal: after this phase you can say in two sentences what the product is and who uses it, and you know
exactly where every piece of UI data comes from.

## Order of sources

| Need | 1st | 2nd | 3rd | 4th | Nothing found |
|---|---|---|---|---|---|
| Project description | text or path in `$ARGUMENTS` | `PROJECT.md` / `project.md` anywhere | `find_docs.py` → `project` candidates (read the top 3) | `package.json` description, landing copy in existing code | Ask for a description and **wait** |
| Backend contract | path/URL in `$ARGUMENTS` | `FRONTEND.md` anywhere | `find_docs.py` → `backend` candidates (read the top 3) + `openapi.*`, `swagger.*`, `*.http`, `*.postman_collection.json` | the backend's route/controller files (read-only) | Ask **Yes / No / Not implemented** |

`find_docs.py` scores files. It doesn't decide. A file is the project description only if it says *what
the product does and for whom*. A file is the backend contract only if it lists endpoints, or messages
with their shapes. A README that only covers installation is neither.

Several partial docs are fine: merge them. Note each source in `DESIGN/project.md`, for example
"Product: notes.txt + README §About; API: docs/api.md + backend/routes/*.ts".

## URLs

Fetch a contract link with WebFetch, and ask it for *every endpoint with its method, path, auth, request
fields and response fields, plus the error format, pagination and base URL*. Save the result as
`DESIGN/contract-from-url.md` so the next run doesn't fetch it again. Write the URL at the top.

## The backend question

Ask it only when nothing is found:

```
question: "I couldn't find a backend contract (FRONTEND.md / API docs). Does this project have a backend the frontend should talk to?"
options:
  - "Yes, I'll provide it": "Wait for a file path, a link or a pasted description of the API"
  - "Not implemented yet": "It will have a backend, but it isn't built. I'll build the UI against mock data and write FRONTEND.md listing the endpoints the backend must provide"
  - "No backend": "Standalone site. Content is static or kept in the browser"
```

Put "Not implemented yet" first and mark it (Recommended) when the project description mentions
accounts, orders, payments, dashboards or other server data. Put "No backend" first and mark it when it
describes a brochure site, portfolio, landing page or a client-only tool.

- **Yes:** stop and wait for the user's next message. Don't build anything yet. When it arrives, treat
  it like the arguments: a path, a URL or text.
- **Not implemented:** `backend_mode = "mock"`. Write `FRONTEND.md` from the template after the plan is
  approved (Phase 4), because then you know every page's data needs.
- **No:** `backend_mode = "none"`. Content goes into typed content files (`src/content/*.ts` or
  Markdown). Interactive state that must persist lives in `localStorage`, behind a small store module.

## What to extract from a contract

Write it into `DESIGN/project.md` under "Data". Per endpoint, record:
- method, path, auth (public / user / role)
- request fields with types, required or optional
- response shape, pagination style (page/limit, cursor), error shape and codes
- realtime channels (WebSocket/SSE events) and the payload of each
- base URL and env var name, CORS or proxy needs, how the auth token is sent (cookie vs header)

Ambiguity that changes the UI (e.g. "does the order list include item names or only IDs?") → ask the
user one batched question. Anything else → pick the safest reading and note it as an assumption.

## Stack detection (existing frontend)

Look at `package.json` and the config files (`next.config.*`, `svelte.config.*`, `vite.config.*`,
`nuxt.config.*`, `astro.config.*`, `angular.json`, `tailwind.config.*` or `@import "tailwindcss"`).
Record the framework, router, styling, component library, state/data library and the package
manager (from the lockfile). Keep all of them, and never migrate frameworks.
