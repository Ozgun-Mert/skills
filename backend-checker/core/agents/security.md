# Security agent → `docs/SECURITY_PROBLEMS.md`

Follow `agent-contract.md` (inputs, JSON output, validation, return line). This brief is your checklist.
Check id: `security`. Use the section ids below exactly.

## Severity

| Level | Use when |
|---|---|
| **Critical** | Exploitable now with no special access, leading to data theft/tampering, account takeover, money loss or remote code execution: SQL injection, live secrets in git, missing ownership check on writes, plaintext passwords, prices taken from the client. |
| **High** | Serious but needs a precondition (a logged-in user, a specific config), or a large blast radius: IDOR on reads, wildcard CORS with credentials, no rate limit on login, JWT without expiry, stack traces to clients, known CVE with a public exploit. |
| **Medium** | Weakens defense in depth or causes wrong data/crashes: missing headers, N+1 on hot paths, missing transaction, enumeration messages, CVE in a code path you don't use. |
| **Low** | Hardening and hygiene. |

Add `owasp` (e.g. `A01 Broken Access Control`) where one fits.

## Work order

1. Read your plan. If `run_tests` is true, **start the tests in the background first**:
   `python "<CORE>/scripts/run_tests.py" --root .` (Bash with run_in_background). If background runs
   aren't available, run it in the foreground at the end with a 600000 ms timeout.
2. Load the code (contract, "Inputs" step 2).
3. Go through the sections below in order, starting from `hotspots` and reading the surrounding code.
4. Before writing JSON, collect the test result:
   `python "<CORE>/scripts/run_tests.py" --root . --wait`.
5. Write `findings-security.new.json`, validate, return the summary line.

In **incremental** mode only sections in `rerun_sections` get a whole-scope look. Everything else is
limited to `files_to_analyze`.

## Sections

### 1. Dependencies & secrets
- **1a – vulnerable or EOL versions.** Read `docs/.backend-checks/deps.json`, produced by
  `osv_check.py` (OSV.dev + endoflife.date).
  - **Vulnerable packages:** one finding per vulnerable package. Put the manifest/lockfile in `file`
    and the package in `symbol`, e.g. `jsonwebtoken@8.5.1`. The problem names the CVE/GHSA ids and
    what they allow.
  - **The fix is the closest safe version:** `recommended_version`, the same major when `same_major`.
    Mention `latest_version` only as context.
    - If `recommended_exists` is false or `some_vulns_unfixed` is true, verify with WebSearch.
    - If no safe version exists, propose a maintained alternative library.
  - **Grouping:** dev-only or transitive packages get one combined finding (list them in `locations`),
    severity one level lower unless reachable at runtime.
  - **Runtime:** EOL runtime (`is_eol`) → finding with the closest supported LTS
    (`supported_lts`/`supported_cycles`).
  - **If deps.json shows `network_ok: false`:** use WebSearch for the direct dependencies only and say
    so in `section_notes`.
- **1b – secrets in git or visible to the frontend.** Use the plan's `secrets` block: `tracked_secret_files`, `history_secret_files`, `history_secret_commits`,
  `source_hits`, `frontend_env`. Report:
  - secret files tracked now;
  - secret files that were committed and later deleted. They're still in history: say "rotate the
    secret; removing the file doesn't remove it from history".
  - hardcoded credentials and fallback secrets (`process.env.X || 'secret'`);
  - secrets exposed to the frontend: `VITE_`/`NEXT_PUBLIC_`/… variables holding secrets, keys in
    frontend code, and API responses that hand secrets to the browser.

  Say whether each secret must be rotated. Only read extra paths here for `frontend_env`/`secrets` hits.

### 2. Database
- **2a – SQL / NoSQL injection.** Every query built with string concatenation, template literals,
  f-strings, `%`/`.format`. Also:
  - `$queryRawUnsafe`/`.raw()`/`text(f"...")` with input;
  - user-controlled column names, `ORDER BY` or operators (`$where`, `$gt` from JSON bodies in Mongo);
  - `LIMIT`/`OFFSET` from raw input.

  An ORM query with bound parameters is fine.
- **2b – illogical or unsafe data operations.** Use the schema/migrations if present. Look for:
  - deleting or updating rows that other tables reference, with no cascade/soft-delete/guard
    (FK errors or orphans);
  - status changes that skip required states;
  - **multi-step writes with no transaction** (order + order items + stock + payment) that leave
    partial state if a step fails;
  - stock/counter updates done as read-modify-write instead of an atomic update.
- **2c – unnecessary database work:**
  - N+1 queries (a query inside a loop);
  - `SELECT *` where few columns are used;
  - filtering, sorting or pagination done in code after fetching everything;
  - the same query repeated in one request;
  - missing indexes on columns used for filters/joins (when the schema is visible);
  - counting by fetching rows.

  The fix explains how to cut load on both the backend and the DB (join, `IN (...)`, batch, select
  columns, push the filter into SQL, add an index).

### 3. Test suite
Use `tests.json` from `run_tests.py`.
- **No suite** (`no_suite`): finding-free section with note `Test suite should be implemented.`
- **Ran:** note `N tests ran, M failed.` plus one finding per failing test (severity by what the test
  protects; default Medium). Title = test name; problem = one simple sentence on why it fails, read
  from `failure_lines`/`tests.log` and the code under test; fix = what to change.
- **Couldn't run** (missing deps, timeout, missing env): note `Could not run: missing X`, no findings.

Never install dependencies to make tests run.

### 4. Logic
- **4a – questionable business rules.** Things that look wrong but might be intended, e.g.:
  - admins can create or delete other admins (including themselves or the last admin);
  - staff can change their own role or restaurant;
  - users can cancel orders after delivery;
  - refunds above the paid amount;
  - coupons that stack without limit.

  Every 4a finding gets `"needs_confirmation": true` and a short `question` ("Should any admin be
  able to delete other admins, including the last one?"). Severity is what it would be if
  unintended. The orchestrator asks the user. Don't ask yourself and don't drop them.
- **4b – logic that can crash or corrupt the system:**
  - division by zero;
  - float math for money;
  - rounding/precision errors, integer overflow;
  - null/undefined access on DB results that can be empty (`rows[0].x`);
  - unhandled promise rejections or async errors in Express 4 handlers (crash or hang);
  - **stale cache:** data cached and served after the source changed, with no invalidation;
  - timezone/date bugs;
  - infinite loops or recursion;
  - race conditions on shared in-memory state.

### 5. Data privacy & authorization
- **5a – access to other users' data.** For every route that takes an id (params, query, body):
  - Does it check that the current user owns or may access that record (`WHERE id = $1 AND
    restaurant_id = $2`, a policy, a scoped query)? Example: staff editing another restaurant's menu
    item because only the item id is checked.
  - Role checks without tenant checks.
  - **Mass assignment:** request bodies spread into create/update so users can set `role`,
    `isAdmin`, `restaurantId`, `ownerId`, `price`, `status`. This includes letting a user change
    their own `restaurantId`.
  - Socket rooms joined by any id.
- **5b – trusting values sent by the frontend.** Prices, totals, discounts, tax, stock, roles or user
  ids taken from the request instead of the DB/session. Example: an order total computed from
  `item.price` sent by the client.
  - Read the extra (frontend) paths' `client_values` hotspots only to confirm what the client sends.
  - Fix: look values up server-side and recompute.

### 6. Data security
- **6a – sensitive data not protected at rest.**
  - Passwords must be hashed with bcrypt/argon2/scrypt (not plain, not md5/sha1/sha256 alone), with
    a sane cost.
  - Reset, refresh and API tokens should be stored hashed.
  - PII (national ID, phone, address, health data) encrypted where appropriate.
  - Card numbers never stored: provider tokens only.
- **6b – responses returning unnecessary data:**
  - password hashes;
  - tokens;
  - internal flags;
  - other users' emails;
  - whole DB rows / `RETURNING *` / ORM objects / `__dict__` sent back without a DTO or serializer.
- **6c – weak cryptography:**
  - md5/sha1 for passwords;
  - low bcrypt cost;
  - `Math.random()`/`random` for tokens, OTPs or IDs;
  - hardcoded keys or IVs;
  - short/default JWT secrets;
  - `algorithms` that include `none`;
  - `jwt.decode` used where `jwt.verify` is needed (this one also goes in 14 if it's the auth path:
    report it once, in 14).

### 7. Upload security
For each upload path check that it does all of these:
- validates the real type by magic bytes, not the extension or `Content-Type`;
- enforces size and file-count limits;
- sanitizes the filename (path traversal) and stores under a random name outside the web root, or in
  a private bucket with signed URLs;
- blocks HTML/SVG/executables or serves them with a safe `Content-Type` + `Content-Disposition: attachment`;
- re-encodes images and strips metadata where relevant;
- defends against decompression/zip bombs.

The goal: no malware reaches object storage, the server or the DB. If there are no uploads, note
`Not applicable (no upload handlers found)`.

### 8. CORS (HTTP and WebSocket)
- `localhost` origins are fine only in dev-only config.
- **Production needs a strict allowlist.** Flag:
  - `*`;
  - reflecting the request origin;
  - `credentials: true` with a wildcard or reflection;
  - regexes/suffix checks that match attacker domains (`endsWith('example.com')`);
  - `null` origin allowed.
- Check Socket.IO/ws/Channels CORS and `Origin` checks separately from HTTP.

### 9. HTTP security headers
- Check that these are set:
  - HSTS;
  - CSP, where the API serves HTML;
  - `X-Content-Type-Options: nosniff`;
  - `frame-ancestors`/`X-Frame-Options`;
  - `Referrer-Policy`;
  - `Cache-Control: no-store` on sensitive responses.
- Check that `X-Powered-By`/server banners are removed.
- Include headers set in in-scope nginx/proxy config.

### 10. Rate limiting
- Both are required:
  - a global API/IP limit;
  - a **per-user** limit for authenticated traffic.
- Stricter limits on login, register, password reset, OTP/verification and email/SMS-sending routes.
- With more than one instance (Docker replicas, serverless, cluster) the store must be shared (e.g.
  Redis), not in-memory.
- WebSocket message floods count too.

### 11. Idempotency / double submission
Find actions that can run twice when the same request is sent again before the first response:
payments, order creation, coupon redemption, refunds, signups, stock decrements. Expect an
idempotency key, a unique constraint, a transaction with row lock (`SELECT ... FOR UPDATE`) or a
state check (`UPDATE ... WHERE status = 'pending'` and checking affected rows). Example: paying twice
for the same order.

### 12. Responses that reveal too much
- **User enumeration** in login, register, password reset and invite:
  - "No user with this email" / "Wrong password" → `Email or password incorrect`;
  - "Email already registered" on reset → a generic "If the account exists, we sent an email".
- Different status codes or timing for existing vs non-existing users count too.

### 13. Helmet or framework equivalent
- Is it installed **and** applied app-wide?
- Is it configured, not just installed (CSP set for HTML responses, HSTS)?
- Equivalents per framework: `references/framework-equivalents.md`.

### 14. Authentication & sessions
- **JWT:** verified with `verify` (not `decode`), algorithm pinned (no `none`, no HS/RS confusion),
  `exp` set and checked, secret strength, refresh-token rotation and revocation, logout invalidating
  tokens/sessions.
- **Cookies:** `HttpOnly`, `Secure`, `SameSite`.
- **Session fixation:** session regenerated on login.
- **Password reset tokens:** random (CSPRNG), single-use, short-lived, stored hashed.
- **Coverage:** routes missing auth middleware entirely.

### 15. Input validation & request limits
- Schema validation (zod/joi/class-validator/pydantic models/serializers) on every endpoint that
  takes input.
- Body size limits (`express.json({limit})`, `client_max_body_size`).
- Pagination caps: no `?limit=1000000`, no unbounded `findMany()`.
- Array length limits.

### 16. Other injection
- Command injection (`exec`, `subprocess(shell=True)`).
- Path traversal (`sendFile`/`open` with user paths).
- SSRF: the server fetching user-supplied URLs or webhooks without an allowlist. Block internal IPs.
- Prototype pollution: deep merge of user JSON, vulnerable lodash.
- ReDoS: user input in `new RegExp`, catastrophic patterns.
- Template injection (`render_template_string`).
- Unsafe deserialization (`pickle`, `yaml.load`, `unserialize`).
- `eval`.

### 17. CSRF
Only relevant when auth rides on cookies. For state-changing routes expect SameSite=Lax/Strict plus a
CSRF token or double-submit/origin check. With header-only bearer auth, note `Not applicable (bearer
tokens, no cookie auth)`.

### 18. Error leakage & misconfiguration
- Stack traces, SQL errors or exception messages returned to clients.
- `debug=True`/`DEBUG = True`/dev error pages in prod config.
- Publicly reachable Swagger/GraphiQL/admin/metrics/actuator/debug endpoints.
- Default credentials.
- Verbose `X-Powered-By`.

### 19. Sensitive data in logs
Passwords, tokens, reset codes, card data, full request bodies, auth headers or PII written to
`console.log`/loggers/`print`.

### 20. Payments & webhooks
- Webhook signature verification (Stripe `constructEvent`, iyzico/PayPal equivalents).
- Amount and currency verified against the provider's record, not the client.
- Replay protection: event id stored and processed once.
- Card data never touching the server (use provider tokens).

### 21. WebSocket authentication & authorization
- Auth on connect (token checked in the handshake).
- Per-room/per-message authorization: can a client join any restaurant's room or emit events for
  data it doesn't own?
- Message validation and size limits.

## Reading extra paths
Only for 1b (`frontend_env`, `secrets` hints), 5b (`client_values` hints) and 8 (if the frontend
config shows the production origin). Read the hinted lines, not whole folders.
