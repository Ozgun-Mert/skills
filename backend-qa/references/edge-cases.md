# Edge cases: what to ask, what never to ask

Rule of thumb: **ask when two reasonable engineers could pick different behavior and a test would
assert one of them.** Don't ask when only one answer is sane; record it as `obvious` instead.

## Never ask (record as `obvious`)

- Wrong password / wrong code / invalid token → not authenticated.
- Anonymous requests to private data or any write → denied (401).
- A user can't read or change another user's private data (the access matrix still decides the
  exact status and any sharing exceptions).
- Malformed JSON, wrong types, missing required fields → 4xx, never 500, nothing written.
- No response ever contains password hashes, secrets, tokens of other users or stack traces.
- Creating something returns it (or its id); reading what you just created returns the same data.
- Deleting something you don't own doesn't delete it.
- Server-owned fields (`id`, `created_at`, `owner_id`, `role`, computed totals) can't be set by
  the client.
- SQL/NoSQL injection strings are treated as plain data.

## Ask (pick the ones the function actually raises)

Each line: the question to ask, then typical options (recommended first).

### Authentication and accounts
- Failed logins: after **how many** attempts, **for how long**, keyed by **account, IP, or both**?
  (*5 / 15 min / both* · *10 / 1 h / IP* · *3 / until reset email*)
- During a lock, is the **correct** password also rejected? Does a successful login reset the
  counter? Is the user emailed?
- Is the IP read from `X-Forwarded-For` (behind a trusted proxy) or the socket only?
- Login error message: same for unknown email and wrong password (no enumeration)?
- Email uniqueness: case-insensitive? Trim spaces? Gmail dots/plus treated as distinct?
- Password rules: min length, max length (bcrypt 72-byte limit), breached-password check?
- Session/JWT lifetime, refresh token lifetime, rotation on refresh, reuse detection?
- What happens to other sessions on password change / logout-all?
- Reset/verify tokens: expiry, single use, does requesting a new one invalidate the old?
- Signup: auto-login? email verification required before login? before which actions?
- Account deletion: immediate or grace period? data erased or anonymized? can the email be reused?

### Arithmetic and money
- Division by zero (or an empty set for averages): *validation error (400)* / *return 0* /
  *return null* / *treat as "N/A"*.
- Rounding: *half-up to 2 decimals* / *banker's rounding* / *always down (floor)*; at which step
  (per line or on the total)?
- Money type: integer minor units vs decimal; currency allowed set; mixed currencies?
- Negative amounts/quantities: rejected, or allowed for refunds/credits?
- Upper limits: max quantity per line, max order total, max transfer amount.
- Remainder when splitting (100 / 3): who gets the extra cent?
- Percentages over 100 or below 0 (discounts, tax): reject or clamp?
- Overflow: very large numbers — reject at what bound?

### Deletion and lifecycle
- Soft delete or hard delete? Can deleted items be restored, by whom, for how long?
- Deleting a parent with children (user with orders, project with tasks): *block with 409* /
  *cascade delete* / *orphan/reassign*.
- Deleting twice (second DELETE): *404* / *204 (idempotent)*.
- Can a user delete themselves? The last admin? An item in use (paid order, active subscription)?
- Allowed state transitions (pending → paid → shipped; can a shipped order be cancelled?).
- Editing after a cutoff (after payment, after shipping, after 24 h)?

### Lists, search, pagination
- Default and max page size; behavior for `limit` above max (*clamp* / *400*).
- Page beyond the end: *empty list* / *404*.
- Default sort order and allowed sort fields; tie-breaker for stable paging.
- Search: case-insensitive? accent-insensitive? partial match? minimum query length?
- Filters with no results vs invalid filter values.

### Strings and identifiers
- Max lengths for names, titles, descriptions, comments.
- Trim whitespace? Collapse internal spaces? Empty after trim = missing?
- Case sensitivity for usernames, slugs, codes, tags.
- Duplicate names allowed (two projects called "Home")? Per user or global?
- Allowed characters in usernames/slugs; Unicode normalization (NFC) and homoglyphs?

### Dates and time
- Time zone of stored and returned dates; input without zone means what?
- Past dates allowed (booking yesterday)? How far in the future?
- End before start; zero-length ranges; overlapping bookings.
- DST transitions, Feb 29, end-of-month recurrence ("every 31st").
- Expiry boundaries: valid **at** the expiry second or not?

### Concurrency and idempotency
- Two buyers, last item: who wins, what does the loser get (409 / waitlist)?
- Double-click submit / retried request: idempotency key required? window? response on replay?
- Concurrent edits: last write wins, or version check with 409?
- Webhook delivered twice / out of order.

### Files and uploads
- Max size; allowed types (checked by content or extension?); image dimensions.
- File name handling (keep, sanitize, replace with random id)?
- Who can download; are links public, signed, expiring?

### Limits, quotas, plans
- Rate limits per endpoint group (requests / window / key) and the response (429 + `Retry-After`?).
- Plan quotas (free: 3 projects): behavior at the limit and after downgrade.
- Invites/sharing limits; self-invite; inviting an existing member.

### Notifications and side effects
- Which actions send email/SMS/push, to whom, and what must **not** be sent (e.g. no email on
  failed reset for unknown address)?
- Side effects on failure: is a failed payment's order kept, cancelled, or retried?

## Writing the question well

Bad: "How should division by zero be handled?"
Good: "`averageRating(productId)` — product has no reviews (0 ratings). What should it return?"
with options *`null`, shown as "No ratings yet" (Recommended)* / *0* / *404 error*.

Bad: "What's the login policy?"
Good: three linked questions in one call: attempts + window, keyed by, correct password during
lock — each with concrete options and "code now: …".
