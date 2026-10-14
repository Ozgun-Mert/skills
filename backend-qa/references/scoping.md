# Scoping: who may reach which data (Phase 3)

Skip this phase only when the backend has no users, no auth and no per-owner data (a public,
read-only API). Otherwise it is mandatory: most serious backend bugs are one user reaching
another user's data.

## 1. Derive candidates from the code (don't ask what you can read)

From the map and the function bodies you already read:
- **Actors:** anonymous, authenticated user, roles (`role` enums, `isAdmin`, guards like
  `@Roles('admin')`, `require_role`), org/tenant membership, API keys, service accounts, webhooks.
- **Resources:** tables/models with an owner column (`user_id`, `owner_id`, `created_by`,
  `org_id`, `tenant_id`), and child resources reached through a parent (`/orders/:id/items`).
- **Actions per resource:** read one, list/search, create, update, delete, export/download,
  special actions (approve, refund, invite, share).
- **What the code does now:** where it filters by owner, where it doesn't, what it returns for
  someone else's id. Show this in option descriptions; never treat it as the answer.

## 2. Ask with options

One round per 2–4 resources, high-risk first. Useful question shapes:

- "Who may read an **order**?" — *Only its owner and admins (Recommended)* / *Anyone in the same
  organization* / *Owner, admins and the assigned courier* / (Other)
- "Can a user **edit** another user's **comment**?" — *No, only the author (Recommended)* /
  *Author and moderators* / *Author, moderators and the post owner*
- "What does a user get when they request **another user's** order by id?" — *404, as if it
  doesn't exist (Recommended)* / *403 Forbidden* (asked once as a global rule `G-n`, not per
  resource, unless the user wants it to differ)
- "What may an **admin** do?" (multiSelect) — *Read all users' data* / *Edit any record* /
  *Delete users* / *Impersonate*
- "Is anything **shared or public**?" — *Nothing, everything is private (Recommended)* /
  *Profiles are public* / *Items can be shared by link* / (Other)
- Multi-tenant: "Can a user belong to several organizations, and switch between them?"

Don't ask "can an anonymous visitor delete orders?". Anonymous write access to private data is an
`obvious` default (denied).

## 3. Record the matrix

In `qa/TEST_DECISIONS.md` → **Access matrix**, one row per resource × action:

| ID | Resource | Action | Allowed | Denied → response | Source |
|---|---|---|---|---|---|
| S-1 | order | read | owner, admin | others → 404, anonymous → 401 | user |
| S-2 | order | list | owner sees own only; admin sees all | — (filtered, never an error) | user |
| S-3 | order | update | owner while status = pending; admin | others → 404 | user |

"Allowed" may carry a condition (status, time window, plan). Conditions become their own tests.

## 4. From matrix to tests

Each `S-n` row expands into the actor checks in `attack-matrix.md` §2 for **every endpoint that
touches that resource**, including list/search/export/count, nested routes, file downloads,
websocket events and background jobs triggered by a request. The worker generates these; the
user isn't asked per endpoint.
