# Performance pattern catalog

Read by the performance agent on demand. Each entry: **pattern → why it's slow → fix**.

Contents: [1. SQL queries](#1-sql-queries) · [2. Algorithmic complexity](#2-algorithmic-complexity) ·
[6. Indexes](#6-database-indexes) · [3, 7–13. Short lists](#short-lists)

## 1. SQL queries

### Round trips
| # | Pattern | Why it's slow | Fix |
|---|---|---|---|
| Q1 | **N+1**: one query for a list, then one per row (a loop or ORM lazy loading in serializers/templates) | N extra round trips; each pays network latency + parse/plan | JOIN, `WHERE id IN (…)` / `= ANY($1)`, eager loading: Prisma `include`, Sequelize `include`, TypeORM `relations`/`leftJoinAndSelect`, Django `select_related`/`prefetch_related`, SQLAlchemy `joinedload`/`selectinload`, GraphQL DataLoader |
| Q2 | INSERT/UPDATE/DELETE **inside a loop** | N statements, N round trips, N commits | One set-based statement: multi-row `INSERT … VALUES (…),(…)`, `createMany`/`bulkCreate`/`bulk_create`/`executemany`/`insert_many`, `UPDATE … SET col = CASE id WHEN … END WHERE id IN (…)`, `UPDATE … FROM (VALUES …)`, COPY for big loads |
| Q3 | **Two UPDATEs on the same row** (one per column) | Two round trips + two row locks | One `UPDATE t SET a = …, b = … WHERE id = …` |
| Q4 | **SELECT then UPDATE** to read-modify-write a value | Two round trips + race condition | `UPDATE … SET stock = stock - $1 WHERE id = $2 AND stock >= $1 RETURNING …` |
| Q5 | **Check then INSERT** ("does it exist? if not, insert") | Two round trips + race | `INSERT … ON CONFLICT DO UPDATE/NOTHING` (Postgres/SQLite), `ON DUPLICATE KEY UPDATE` (MySQL), ORM `upsert` |
| Q6 | **INSERT then SELECT** to get the new row | Extra round trip | `INSERT … RETURNING *` (Postgres/SQLite), `OUTPUT` (SQL Server) |
| Q7 | **COUNT query + page query** for every list | Two scans | `COUNT(*) OVER()` in the page query, or drop exact totals (keyset + "has more") |
| Q8 | **Identical query repeated** within one request (e.g. current user loaded in middleware and again in the handler) | Wasted round trips | Load once, pass it along; request-scoped memoization |
| Q9 | **One autocommit per statement** in a loop | An fsync per commit | Wrap the batch in one transaction (also makes it atomic) |

### Reading too much
| # | Pattern | Why it's slow | Fix |
|---|---|---|---|
| Q10 | `SELECT *` or full ORM entities when a few columns are used | More I/O, network and memory; prevents index-only scans | Explicit columns / projections: Prisma `select`, Django `.only()`/`.values()`, SQLAlchemy `load_only`, TypeORM `select` |
| Q11 | Loading big BLOB/TEXT/JSON columns that aren't used | Large rows over the wire | Defer them (`defer`, separate table, `select` without them) |
| Q12 | Fetch everything, then **filter/sort/paginate in code** | Reads the whole table | Push into SQL: `WHERE`, `ORDER BY`, `LIMIT` |
| Q13 | Fetch rows to **count/sum/average** in code | O(n) transfer for one number | `COUNT`/`SUM`/`AVG` … `GROUP BY` in SQL |
| Q14 | `COUNT(*) > 0` to test existence | Counts every match | `EXISTS (…)` / `LIMIT 1` / ORM `exists()` |
| Q15 | `findMany()[0]` / `.all()[0]` for one row | Reads all matches | `findFirst`/`.first()`/`LIMIT 1` |
| Q16 | **Unbounded queries** with no LIMIT on growing tables | Grows with data, until timeouts | `LIMIT` + pagination; max page size |
| Q17 | Deep **`OFFSET` pagination** (`OFFSET 100000`) | DB still reads and discards the skipped rows | Keyset/cursor pagination `WHERE (created_at, id) < ($1, $2) ORDER BY … LIMIT n` |

### Index-hostile queries
| # | Pattern | Why it's slow | Fix |
|---|---|---|---|
| Q18 | **Function on an indexed column** in WHERE (`LOWER(email) = …`, `DATE(created_at) = …`, `col + 1 = …`) | Index can't be used (non-sargable) | Rewrite as a range (`created_at >= day AND < next_day`), or a functional/expression index (`CREATE INDEX … ON users (LOWER(email))`), or a `citext` column |
| Q19 | **Leading-wildcard LIKE** (`LIKE '%term%'`) | Full scan | Trigram index (`pg_trgm` GIN), full-text search (`tsvector`, MySQL FULLTEXT), or a search engine for big catalogs |
| Q20 | **Implicit type casts** (varchar column compared to an int, uuid vs text) | Index skipped | Compare with the column's type; fix the column type |
| Q21 | `OR` across different columns | Often a full scan | `UNION ALL` of two indexed queries, or an index per column |
| Q22 | Huge `IN (…)` lists (thousands of literals) | Parse/plan cost, plan cache misses | `= ANY($1::int[])`, a temp table/VALUES join, chunk into batches of ~500–1000 |
| Q23 | `NOT IN (subquery)` | Slow plans; also wrong with NULLs | `NOT EXISTS` |
| Q24 | **Correlated subquery** run per row in the SELECT list | N inner queries | JOIN + GROUP BY, `LATERAL` join, window functions |
| Q25 | `SELECT DISTINCT` hiding duplicates from a bad JOIN | Sorts/hashes the whole result | Fix the join or use `EXISTS` |
| Q26 | `ORDER BY RAND()`/`RANDOM()` on big tables | Sorts the whole table | Random id range, `TABLESAMPLE`, or a precomputed random column |

### Writes and plans
| # | Pattern | Why it's slow | Fix |
|---|---|---|---|
| Q27 | ORM `save()` writing **every column** | Bigger writes, more WAL, lost-update risk | Update only changed fields (`update_fields`, `update({…})`, dirty tracking) |
| Q28 | **Long transactions** holding locks across network calls (e.g. a payment API call inside a transaction) | Blocks other writers | Keep transactions short; do external calls before/after |
| Q29 | **Dynamic SQL strings** (values concatenated, different text per call) | Plan cache misses, plus injection risk (security's job) | Prepared/parameterized statements |
| Q30 | **Heavy aggregates** (dashboards, leaderboards) recomputed per request | Repeated full scans | Materialized view, summary table updated on write or on a schedule, or cache (section 3) |

### MongoDB and other NoSQL
| # | Pattern | Fix |
|---|---|---|
| Q31 | No projection | Use a projection |
| Q32 | Unanchored/case-insensitive `$regex` | Anchored regex + index, or Atlas Search |
| Q33 | `$lookup` or `find` inside loops | `$in` batch, or embed |
| Q34 | Unbounded `find({})` | `limit` + range pagination |
| Q35 | Unindexed sort | Index matching the sort |
| Q36 | Count with `countDocuments({})` on big collections | `estimatedDocumentCount` |
| Q37 | Redis `KEYS *` | `SCAN` |
| Q38 | Many Redis round trips | Pipelines / `MGET` |

## 2. Algorithmic complexity

| # | Pattern | Complexity now → after | Fix |
|---|---|---|---|
| A1 | `list.includes/indexOf/find`, `x in list`, `.index()` **inside a loop** | O(n·m) → O(n+m) | Build a `Set`/`Map`/`dict` once, then O(1) lookups |
| A2 | **Nested loops joining two collections** by key | O(n·m) → O(n+m) | Index one side by key (hash join) |
| A3 | **Sorting inside a loop**, or re-sorting the same data per request | O(k·n log n) | Sort once; keep a heap (`heapq`, priority queue) for top-k |
| A4 | **Hand-written O(n²) sort** (bubble/selection/insertion) | O(n²) → O(n log n) | Built-in sort (Timsort/introsort, native). If hand-written is intentional: heap sort (O(n log n), O(1) extra memory, not stable) or merge sort (stable, O(n) memory) |
| A5 | **Recursion recomputing the same subproblems** (naive Fibonacci, path counting) | Exponential → O(n) | Memoization (`functools.lru_cache`, a Map) or bottom-up DP |
| A6 | **String concatenation in a loop** (Python/Java/Go immutable strings) | O(n²) copying → O(n) | `''.join(parts)`, `StringBuilder`, `strings.Builder` |
| A7 | `shift()`/`unshift()`/`pop(0)`/`insert(0, x)` **in a loop** | O(n) each → O(n²) total | `collections.deque`, an index pointer, or reverse then `pop()` |
| A8 | **Regex compiled inside a loop** or per request | Repeated compile | Compile once at module level |
| A9 | **Deep copy / JSON round-trip** (`JSON.parse(JSON.stringify(x))`, `copy.deepcopy`) in loops or per request on big objects | O(size) per call | Avoid the copy, copy shallowly, or use `structuredClone` once |
| A10 | Repeated **linear scans for min/max/sum** over the same list | O(k·n) → O(n) | One pass, or keep running values |
| A11 | **Quadratic de-duplication** (`filter((x, i) => arr.indexOf(x) === i)`) | O(n²) → O(n) | `new Set(arr)` / `dict.fromkeys` |
| A12 | **Building a big list just to iterate once** | O(n) memory → O(1) | Generators/iterators/streams |
| A13 | **Growing arrays/lists of unknown size** in hot loops (Go, Java) | Repeated reallocation | Preallocate capacity when the size is known |

Only report what matters at realistic input sizes (rows in growing tables, per-request lists,
user-supplied arrays).

## 6. Database indexes

### Missing indexes
- Columns in `WHERE` equality/range conditions on large or growing tables.
- Foreign keys. Postgres does not index them automatically, so JOINs and `ON DELETE` cascades scan.
- `ORDER BY` + `LIMIT` columns (an index lets the DB stop early).
- Composite queries: index `(equality_cols…, range_or_sort_col)` in that order.
- Covering indexes (`INCLUDE (…)`) for hot read-only queries, to get index-only scans.
- Partial indexes for hot subsets (`WHERE status = 'pending'`, `WHERE deleted_at IS NULL`).
- Expression indexes for Q18. Trigram/GIN indexes for Q19 and for JSONB containment queries.

### Problem indexes
- **Redundant:** `(a)` when `(a, b)` exists; the same index twice under different names.
- **Low selectivity alone** (booleans, status with 3 values), unless partial.
- **Unused indexes on write-heavy tables:** each one slows every INSERT/UPDATE.

### Unique constraints
They double as indexes and prevent duplicate rows (emails, slugs, `(order_id, product_id)`).

Fix format: the `CREATE INDEX CONCURRENTLY idx_… ON table (cols);` statement, plus which query it
speeds up.

## Short lists

### 3. Caching
- **Candidates:**
  - reference data (categories, menus, settings, permissions);
  - expensive aggregates;
  - third-party lookups (exchange rates, geo);
  - rendered fragments;
  - per-user session/profile data read on every request.
- **Layers:**
  - in-process LRU (single instance; fastest; lost on restart);
  - Redis/Memcached (shared across instances);
  - HTTP/CDN (section 12);
  - DB materialized views (Q30).
- **Always specify:** key design, TTL, invalidation on write (delete or update the key in the same
  code path that writes), stampede protection for hot keys (lock or `stale-while-revalidate`), and
  a size limit.

### 7. Pagination & payload size
- Max page size; cursor pagination (Q17).
- Response DTOs without unused fields or nested graphs.
- gzip/brotli (`compression`, `GZipMiddleware`, nginx `gzip on`).
- Avoid base64 blobs in JSON (use URLs).
- Sparse fieldsets (`?fields=`) for heavy resources.

### 8. Async & blocking work
- **Node:** no `*Sync` APIs in handlers; CPU-heavy work (bcrypt with a high cost on many requests,
  image resizing, big JSON) goes to worker threads or a queue.
- **Python async:** no `requests`/`time.sleep`/sync DB drivers in `async def`; use
  `httpx.AsyncClient`, `asyncio.sleep`, async drivers, or `run_in_executor`. Sync FastAPI
  endpoints (`def`) run in a threadpool and are fine for sync drivers.
- **Concurrency:** `Promise.all`/`asyncio.gather` with a concurrency limit (`p-limit`, a
  semaphore) for independent I/O.
- **Background jobs:** BullMQ, Celery, RQ, Dramatiq, Sidekiq, a cloud queue; or simple
  fire-and-forget after the response for non-critical work.

### 9. Connection pooling & timeouts
- **One pool per process,** created at startup:
  - `pg.Pool`, a Prisma client singleton, SQLAlchemy engine + `pool_size`/`max_overflow`,
    HikariCP;
  - Redis clients reused;
  - `requests.Session`/`httpx.Client` reused;
  - an HTTP agent with `keepAlive`.
- **Serverless or many replicas:** use PgBouncer/RDS Proxy/Prisma Accelerate, since every instance
  opens its own pool.
- **Timeouts everywhere:**
  - HTTP (connect + read);
  - DB `statement_timeout`/`lock_timeout`;
  - Redis command timeout;
  - an overall request deadline;
  - circuit breakers for flaky dependencies.

### 10. Memory usage
- Stream big results (server-side cursors, `yield_per`, `cursor()`, `QueryStream`, Mongo cursors)
  and big files (`createReadStream`, chunked reads).
- Bounded caches (`lru-cache` with `max`, `cachetools.TTLCache`).
- Remove listeners/intervals on teardown.
- Stream uploads to storage instead of buffering (`multer.memoryStorage` for big files is a smell).
- Watch module-level dicts used as caches.

### 11. External API calls
- Batch endpoints; caching responses (section 3).
- Retries with exponential backoff + jitter and a max attempt count; idempotency keys on retried
  writes.
- Timeouts (section 9).
- Move non-critical calls (analytics, notifications, webhooks) off the request path.

### 12. HTTP caching & CDN
- `Cache-Control: public, max-age=…, stale-while-revalidate=…` on public GETs.
- `ETag`/`Last-Modified` + 304 responses.
- `Cache-Control: private, no-store` for personal data.
- Long `max-age` + fingerprinted filenames for static assets.
- Serve uploads from object storage + CDN (signed URLs for private files), not through the app.
- Let nginx/the CDN serve static files.

### 13. Cold start & startup
- Lazy-import heavy modules used by a single route.
- Don't run migrations/`sync({ alter: true })`/`create_all` on every boot in production.
- Load ML models once per process (not per request), and consider a separate model service.
- Keep serverless bundles small; provisioned concurrency / min instances for latency-critical
  paths.
- Build lookup tables, compile regexes and templates, and read config once at startup.
