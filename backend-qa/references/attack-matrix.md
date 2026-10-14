# Attack matrix: try to break every endpoint

The worker runs this checklist against **every** route. These tests are generated from the
access matrix (`S-n`), the global rules (`G-n`) and the function decisions; they are not asked
one by one. Each generated test still cites the decision that defines the expected result, so it
is never a guess. When no decision covers a case and the answer isn't `obvious`, it's a missing
question: you ask it in Phase 4, the worker never invents it.

The core rule behind all of it: **the backend must not trust anything the client sends that it
can work out itself** (who the user is, what they own, prices, roles, totals, timestamps).

## 1. Input attacks (every endpoint with input)

| Case | Examples | Expected (unless a decision says otherwise) |
|---|---|---|
| Missing required field | omit each required field one at a time; empty body | validation error per `G-n`, nothing written |
| Wrong type | string for number, number for string, object for array, `null`, boolean for id | validation error |
| Out of range | 0, -1, huge (2^53, 1e308), NaN/Infinity as strings, decimals where integers expected | per the function's decisions (ask limits in Phase 4) |
| Length | empty string, whitespace-only, 1 char over the max, 1 MB string | per decisions; never a 500 |
| Format | bad email, bad UUID/ObjectId, invalid date, `2024-02-30`, wrong enum value | validation error, not 500 |
| Unicode | emoji, RTL, zero-width, combining chars, homoglyphs in usernames | stored and returned intact, or rejected per decision |
| Injection probes | `' OR 1=1--`, `{"$ne": null}`, `{"$gt": ""}` in JSON fields, `../../etc/passwd` in file names, `<script>` in text fields | treated as data: no extra rows, no error leak, no path escape |
| Extra / unknown fields | `isAdmin: true`, `role: "admin"`, `owner_id`, `user_id`, `tenant_id`, `price`, `total`, `status: "paid"`, `verified: true`, `created_at` | ignored or rejected per `G-n`; **never applied** (mass assignment) |
| Prototype pollution (JS) | `{"__proto__": {"isAdmin": true}}`, `constructor.prototype` | no effect on later requests |
| Oversized body | body above the server limit | 413 or validation error, server keeps working |
| Malformed body | invalid JSON, wrong content type | 4xx, never 500 |
| Query abuse | `limit=100000`, `limit=-1`, `page=-5`, `sort=password`, `fields=password_hash` | capped/rejected per `G-n`; secret fields never returned |
| Duplicate params | `?id=1&id=2`, arrays where scalars expected | deterministic, no bypass |

A **500 response or a stack trace for any client input is always a finding**: the expected result
for bad input is a 4xx with a generic error body (`obvious` default).

## 2. Access attacks (every endpoint that touches owned or restricted data)

Actors, created fresh in each test: **owner A**, **other user B** (same role), **lower role**,
**admin** (if any), **anonymous**, **other tenant** (if multi-tenant), **expired/forged token**.

| Case | How | Expected |
|---|---|---|
| Anonymous | no token/cookie | 401 per `G-n` (or public per `S-n`) |
| Expired / forged token | expired JWT, wrong signature, `alg: none`, token of a deleted user, token after logout/password change | 401 |
| IDOR: other user's id in **path** | B calls `GET/PUT/PATCH/DELETE /orders/{A's id}` | per `S-n` (usually 404), and A's data unchanged afterwards |
| IDOR: other user's id in **body/query** | B sends `{"user_id": A}`, `?owner=A`, `{"order_id": A's}` in a nested action | ignored or denied; B never reads or changes A's data |
| Nested resource | B calls `/orders/{A's order}/items/{item}`; or B's order id with A's item id | denied per the parent's `S-n` row |
| List / search / export / count | B lists, searches with A's name/email, exports, counts | only B's rows; counts don't reveal A's rows |
| Lower role on admin routes | user calls every admin endpoint | 403 per `G-n` |
| Role escalation | user updates own profile with `role: "admin"` / `isAdmin: true` | field ignored; next request still a user |
| Tenant crossing | org X user with org Y resource ids, or switching `X-Org-Id` header to Y | denied |
| Enumeration | sequential ids, `GET /users/{n}`, signup/reset with existing vs new email | no difference that reveals existence (if `G-n` says so) |
| Ownership after transfer/delete | resource deleted or reassigned, old owner retries | per decisions |

Every IDOR test asserts **two things**: the response status/body, and that the victim's data in the
DB is unchanged (for writes) or wasn't returned (for reads).

## 3. Trust attacks (business logic)

| Case | Example | Expected |
|---|---|---|
| Client-sent price/total | order with `price: 0.01`, `total: 1`, `discount: 100` | server computes from DB; client values ignored |
| Client-sent quantity tricks | `quantity: -1`, `0`, `1.5`, huge | per decisions |
| Client-sent identity | `userId` in body for "my" endpoints | server uses the session user |
| Client-sent state transitions | `status: "paid"` / `"shipped"` on update | rejected or ignored; only allowed transitions per decisions |
| Coupon/credit abuse | same coupon twice, expired coupon, coupon of another user | per decisions |
| Double submit / replay | same request twice in parallel; same idempotency key twice; replayed webhook | one effect only (if decided); second returns the first result or 409 |
| Race on limited stock/balance | two parallel buys of the last item; parallel withdrawals | never oversold / never negative (if decided) |
| Webhook forgery | missing/invalid signature, old timestamp, signature for another body | 400/401, no state change |

## 4. Abuse attacks (rate limits, lockouts, sizes)

Only where a decision gives the numbers (asked in Phase 4, see `edge-cases.md`):
- N failed logins → lock/ban per decision (per account? per IP? both?), unlock after the window
  (use a fake clock), success resets the counter (if decided).
- Rate-limit bypass: rotate `X-Forwarded-For` / `X-Real-IP`; the limit must still apply unless
  the app is configured to trust a proxy and the decision says so.
- Reset/verification tokens: single use, expiry, invalid after password change, not guessable
  (length/charset), not returned in responses.
- Upload limits: size just over the cap, wrong MIME vs extension, double extension `a.jpg.php`,
  path in file name.

## 5. Output checks (every response)

- No secret fields in any response: password hashes, tokens, reset codes, internal ids the
  decisions mark private, other users' emails/phones.
- Error bodies don't leak stack traces, SQL, file paths or library versions.
- List endpoints apply the documented default and max page size.
