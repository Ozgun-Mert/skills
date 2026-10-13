# Performance agent → `docs/PERFORMANCE.md`

Follow `agent-contract.md` (inputs, JSON output, validation, return line). This brief is your checklist.
Check id: `performance`. Use the section ids below exactly.

## Purpose and limits

Find what makes the backend slower or more expensive to run than it needs to be, and say how to fix
it. Security problems and readability are other checks: skip them even when you notice them.

**Fixes are plans, not code.** Each fix explains:
- what to change, where, and in what order;
- how much faster, cheaper or lighter it gets, and why. Use complexity, round trips, rows read or
  bytes sent; e.g. "1 query instead of N+1, so 101 → 2 round trips for 100 orders".

No code blocks over ~5 lines; a one-line SQL or index statement is fine.

Each finding has:
- `impact`: **High** if it's on a hot path (every request or every list page), it's O(n²) or worse
  on data that grows, or it causes cross-region round trips; **Medium** if it's real but bounded;
  **Low** if it's a micro-gain;
- `effort`: **S** under an hour, **M** up to a day, **L** more;
- optionally `group` for findings that belong to one change (e.g. `orders-n-plus-1`).

One finding per problem; put the other occurrences in `locations`.

## Work order

1. Read your plan, then load the code (contract, "Inputs" step 2).
2. Run `python "<CORE>/scripts/profile.py" show --root .` and use its `profile`:
   - `scale`, `purpose` and `handwritten_algorithms_intentional`;
   - if a value is `unknown`, say what you assumed in that section's note.
3. Read the script outputs. They're candidates with false positives and gaps: confirm each one in the
   code, and also report what they can't see.
   - `docs/.backend-checks/perf-candidates.json`: loop/query/async/memory/startup candidates plus
     `infra` facts (compression, static files, cache libraries);
   - `docs/.backend-checks/net.json`: hosts, regions and timings for section 5.
4. Go through the sections. For the full pattern lists, read
   `<CORE>/references/performance-patterns.md`, at least the parts for sections 1, 2 and 6 the first
   time.
5. Write `findings-performance.new.json`, validate, return the summary line.

In incremental mode only sections in `rerun_sections` get a whole-scope look. Everything else is
limited to `files_to_analyze`.

## Sections

### 1. SQL queries
Every query on a hot path, judged against the SQL catalog in `performance-patterns.md`. Typical cases:
- **N+1:** a query inside a loop, including ORM lazy loads.
- **Writes in a loop:** several UPDATE/INSERT statements in a loop where one bulk or set-based
  statement would do. Example: updating 2 columns per row with 2 statements inside a for loop.
- **`SELECT *`** or whole entities when one column is used.
- **Two queries where one is enough:** SELECT then UPDATE, check then INSERT, count + list.
- **Work done in code instead of SQL:** filtering, sorting, paging or aggregating after fetching
  everything.
- **Deep `OFFSET` pagination; non-sargable WHERE clauses.**

Candidates: `query_in_loop`, `write_in_loop`, `select_star`, `unbounded_query`. Name the exact
statement and the replacement (JOIN / `IN` / bulk / `RETURNING` / upsert / projection / window
function / keyset). Missing indexes go in section 6, not here.

### 2. Algorithmic complexity
Functions whose time or memory complexity can drop. Candidates: `nested_loops`,
`membership_in_loop`, `sort_in_loop`, `handwritten_sort`, `recursion_no_memo`,
`string_concat_in_loop`, `pop_front_in_loop`. State the current and target complexity, e.g.
O(n·m) → O(n+m) by indexing one side in a Map/Set.

**Built-ins vs hand-written algorithms:**
- **If `handwritten_algorithms_intentional` is false:** recommend the language's built-in (Python
  Timsort `sorted`, JS `Array.prototype.sort`, Go `slices.Sort`, Java `Arrays.sort`…). Built-ins are
  O(n log n) and implemented natively.
- **If it is true** (course or learning project): don't suggest built-ins. Suggest the better
  algorithm instead: bubble/selection/insertion sort → heap sort (O(n log n) time, O(1) extra
  memory) or merge sort (stable, O(n) memory), and say why.

Only report what matters at realistic input sizes. A double loop over 5 config entries is not a
finding.

### 3. Caching
- **What to cache:** data read on many requests but rarely changed, e.g. menus, product catalogs,
  settings, feature flags, permissions, exchange rates, third-party lookups. Candidates:
  `uncached_get_routes`; `infra.cache_libraries` tells you whether a cache already exists.
- **Each finding gives:**
  - what to cache and where: in-process LRU for single-instance apps, Redis when there are several
    instances or the data is shared;
  - the key;
  - the TTL;
  - **how the cache is invalidated on writes.** A cache without invalidation causes stale-data
    bugs.
- Also flag caches that exist but are never hit, or that have a TTL so short they don't help.
- Stale-cache correctness bugs belong to the security check (4b); don't duplicate them.

### 4. Architecture (database, language, framework, libraries)
Is the stack a good fit for **this** project's scale (`profile.scale`) and domain (`profile.purpose`)?
- **If `research_fresh` is true** in your plan, reuse `research_file` and don't search again.
- **Otherwise:**
  1. WebSearch what comparable projects in this domain and at this scale use.
  2. Check the libraries this one uses for faster maintained successors.
  3. Save a short summary to `research_file`: `{"researched_at": ISO date,
     "stack_fingerprint": <plan's stack_fingerprint>, "domain": …, "scale": …, "sources": [urls],
     "summary": …}`.

  Only package names, the domain and the scale go into searches, never code.

What to report:
- **Database fit:**
  - a heavy managed DB (Postgres cluster, Mongo Atlas) for a hobby/small single-instance project
    where SQLite would do, with lower latency and cost;
  - or the reverse, SQLite under concurrent writes from several instances.
- **Outdated or slow libraries with a clearly faster maintained replacement:**
  - Python: `json` on a hot path → `orjson`; `requests` in async code → `httpx`; sync drivers in an
    async app → async drivers;
  - Node: `moment` → `date-fns`/`dayjs`; `request` (deprecated) → `undici`/`fetch`; Express on very
    high throughput → Fastify;
  - …plus anything similar you find.
- **Language or runtime:** only when the domain clearly favors another one, as comparable projects
  show. E.g. heavy numeric/crypto analytics in pure Python loops → Rust/Go service or
  NumPy/Polars; an AI/ML project away from Python loses the ecosystem.
  - Never "rewrite it in C/assembly".
  - Never a full rewrite for a small gain.
  - Prefer the cheapest change, e.g. moving one hot path to a native library.
- **Upgrades:** an old major version of the runtime or framework that is measurably slower than the
  current one (e.g. Python 3.7 → 3.12+ is substantially faster). Version security is the security
  check's job (1a); here only speed counts.

### 5. Connections & infrastructure latency
Use `net.json`:
- `endpoints`: host, port, kind, local/remote, geo, TCP time;
- `region_hints` from IaC;
- `domain`: timings of the public URL and its edge headers;
- `pairs`: distance and estimated RTT;
- `measured_from`.

Report:
- **Components far apart:** DB, backend and cache in different regions or continents (e.g. DB in
  the USA, backend in Frankfurt, Redis in Asia). Each query then pays the cross-region RTT
  (`pairs.est_rtt_ms`), multiplied by the queries per request. Fix: co-locate in one region, or
  add a read replica / cache near the backend.
- **A slow public URL:** high `ttfb_ms` with low connect/TLS times means the server is slow
  (cold start, undersized instance, slow queries); high connect/TLS times mean distance or network.
  Compare `/` against the health path.
- **Timings are measured from the user's machine** (`measured_from`), not from the server. Say so,
  and judge server-to-server links by region and distance, not by these timings.
- **Behind a CDN** (cf-ray, x-vercel-id…): the geo-IP is the edge, not the origin.
- **Nothing found:** if `net.json` has no endpoints, hints or domain, leave the section empty with
  the note `No deployment information found (pass --url or add region config to measure).` Don't
  guess regions.

### 6. Database indexes
Read the schema/migrations/ORM models (`db` hotspots point to the queries). Report:
- **Missing indexes:** columns used in WHERE, JOIN, ORDER BY or GROUP BY on tables that grow (orders,
  users, events, logs). That includes foreign keys, which Postgres doesn't index automatically, and
  columns in the non-sargable patterns from section 1.
- **Composite index order:** equality columns first, then range/sort.
- **Duplicate or redundant indexes:** an index that is a prefix of another.
- **Indexes on write-heavy tables that no query uses.**
- **Unique constraints that should exist and would double as an index.**

Give the `CREATE INDEX` statement in the fix. If no schema is visible, note that in the section.

### 7. Pagination & payload size
- **Unbounded lists:** endpoints that return everything (`unbounded_query`, no `limit`/`take`, no
  max page size).
- **Oversized responses:** JSON with unused or nested data (whole ORM objects, base64 blobs, deep
  includes).
- **Compression:** none on text responses (`infra.compression` empty), and no gzip/brotli at the
  proxy.
- **Overfetching:** N separate calls the frontend has to make, where one endpoint would serve the
  screen. Only if the frontend path was given.

Fix: cursor/keyset pagination with a max page size, response DTOs, compression middleware.

### 8. Async & blocking work
- **Blocking work in async code:** blocking I/O or CPU-heavy work inside async handlers
  (`blocking_in_async`, `sync_io_in_handler`). Examples: `requests`/`time.sleep`/sync DB calls in
  `async def`, `fs.*Sync` in Express handlers, big JSON or crypto work on the event loop. One slow
  call stalls every request on that worker.
- **Serial awaits:** independent `await`s run one after another (`await_in_loop`) that could run
  together (`Promise.all`, `asyncio.gather`, with a concurrency limit).
- **Slow side work inside the request:** sending email/SMS, image processing, PDF generation,
  webhooks. These belong in a background queue (BullMQ, Celery, RQ, Sidekiq…) or at least run after
  the response.

### 9. Connection pooling & timeouts
- **Clients created per request or per call** (`client_per_call`): DB pools, Redis, HTTP sessions,
  SMTP, SDK clients. Create them once at startup and reuse them.
- **Pool configuration:** missing or wrong pool size. Too small queues requests; too large exhausts
  DB connections, especially with serverless or many replicas, where a pooler such as PgBouncer
  helps.
- **No HTTP keep-alive or connection reuse.**
- **No timeout** on outbound calls (`http_no_timeout`), DB statements or locks. One hung dependency
  then holds workers forever. Give concrete timeout values.

### 10. Memory usage
- **Whole-dataset loads:** whole tables (`.all()`/`fetchall()`/`find({})`) or whole files
  (`whole_file_read`) loaded into memory to process them. Use streaming, cursors or batching
  instead.
- **Unbounded in-process caches:** module-level dicts/Maps/lists that grow forever
  (`unbounded_module_cache`). Use an LRU with a max size and TTL.
- **Leaks:** event listeners or intervals added per request; closures holding large objects.
- **Large uploads buffered in memory** instead of streamed to storage.

### 11. External API calls
- **Calls in loops:** third-party calls inside loops (`http_in_loop`) where the API has a batch
  endpoint.
- **Repeated calls:** the same call made on every request when its result could be cached (link
  to section 3).
- **Retries:** no retry with backoff and jitter for transient errors, or retries with no limit.
- **Critical path:** calls that don't need to block the response (move them to a queue or run them
  after the response).

### 12. HTTP caching & CDN
- **Cacheable GETs without headers:** public catalogs, images, config. Add `Cache-Control`
  (`public, max-age`, `stale-while-revalidate`) and `ETag`/`Last-Modified` with 304 support.
  `net.json` `domain.edge_headers` shows what is actually sent.
- **Static files and user uploads served by the app process** (`infra.static_served_by_app`): serve
  them from object storage + CDN, or let the reverse proxy serve them.
- **Private data:** private responses need `private`/`no-store`. Mention this when suggesting
  public caching.

### 13. Cold start & startup
- **Heavy work at import/startup** (`startup_work`): model loading, big file reads, schema sync or
  migrations on every boot, network calls at import time. Serverless cold starts make each one
  visible to users.
- **Per-request work that could run once at boot:** compiling regexes/templates, building lookup
  tables, reading config files, creating clients (link to section 9).
- **Heavy dependencies imported on every path but used by one route:** lazy-import them.

## Finish
You don't write the roadmap: the renderer orders all findings by impact ÷ effort and groups them by
`group`. Your part is setting `impact`, `effort` and `group` carefully.
