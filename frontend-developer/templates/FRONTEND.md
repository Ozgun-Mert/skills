# FRONTEND.md: backend contract for <project>

> Written by /develop-frontend on <date> because the backend was **not implemented yet**.
> The frontend currently runs on mock data (`API_MODE=mock`). Implement these endpoints exactly and
> switch the frontend to the real backend with `API_MODE=http` and `<VITE_/NEXT_PUBLIC_/PUBLIC_>API_URL=<base url>`.
> Status: `planned` → `implemented` → `verified` (update per endpoint).

## Conventions
- Base URL: `<env var>` (dev: `http://localhost:8000`), all paths below are relative to it, e.g. `/api/...`.
- Format: JSON (`Content-Type: application/json`), UTF-8, dates ISO 8601 UTC, money as integer minor units
  + `currency` (e.g. `{"amount": 24000, "currency": "TRY"}`), ids as strings.
- Auth: <none | session cookie (httpOnly, SameSite=Lax) | `Authorization: Bearer <token>`>. Which endpoints need it is
  listed per endpoint.
- Errors: every non-2xx returns
  ```json
  {"error": {"code": "validation_error", "message": "Human readable", "fields": {"email": "Already registered"}}}
  ```
  Codes the UI handles: 400 validation_error, 401 unauthenticated, 403 forbidden, 404 not_found, 409 conflict,
  429 rate_limited, 500 internal.
- Pagination: `?page=1&limit=20` → `{"items": [...], "page": 1, "limit": 20, "total": 134}` <or cursor style>.

## Endpoints

### <METHOD> <path>
- **Used by:** `<route>` (<component>), purpose in one line
- **Auth:** public | user | role:<admin>
- **Request:** path/query params; body
  ```json
  {}
  ```
- **Response 200/201:**
  ```json
  {}
  ```
- **Errors:** 404 when …, 409 when …
- **Status:** planned

<!-- one section per mock client function; keep the same order as src/lib/api/mock.ts -->

## Realtime (if any)
- Channel/event name, payload, who receives it.

## Requested by the frontend
Endpoints or fields the UI needs that an existing contract did not offer (contract mode only).
