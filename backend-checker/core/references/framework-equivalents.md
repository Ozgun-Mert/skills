# Framework equivalents (security sections 8, 9, 10, 13, 15, 17)

Use the row for the detected framework. If the stack isn't listed, find the idiomatic equivalent and
name it in the fix.

| Framework | Security headers (13/9) | CORS (8) | Rate limiting (10) | Validation (15) | CSRF (17) | Body limit (15) |
|---|---|---|---|---|---|---|
| Express | `helmet` | `cors` with an origin allowlist function | `express-rate-limit` + `rate-limit-redis`, or `rate-limiter-flexible` | `zod`/`joi`/`celebrate`/`express-validator` | `csrf-csrf` (csurf is deprecated) | `express.json({ limit: '100kb' })` |
| Fastify | `@fastify/helmet` | `@fastify/cors` | `@fastify/rate-limit` (Redis store) | JSON schema on routes / `zod` type provider | `@fastify/csrf-protection` | `bodyLimit` option |
| NestJS | `helmet` via `app.use(helmet())` | `app.enableCors({ origin: [...] })` | `@nestjs/throttler` (Redis storage) | `ValidationPipe` + `class-validator` (`whitelist`, `forbidNonWhitelisted`) | `csrf-csrf` | `bodyParser` limit |
| Koa | `koa-helmet` | `@koa/cors` | `koa-ratelimit` | `zod`/`joi` | `koa-csrf` | `koa-body` limits |
| Next.js API / route handlers | `headers()` in `next.config.js` or middleware | middleware / route headers | `@upstash/ratelimit` or middleware | `zod` | SameSite cookies + origin check | `bodyParser.sizeLimit` |
| Socket.IO | n/a | `new Server(http, { cors: { origin: [...] } })` + `allowRequest` | per-socket counters / `rate-limiter-flexible` | validate every event payload | n/a | `maxHttpBufferSize` |
| Django | `SecurityMiddleware` + `SECURE_*` settings, `django-csp` | `django-cors-headers` (`CORS_ALLOWED_ORIGINS`) | `django-ratelimit`, DRF throttling (`DEFAULT_THROTTLE_RATES`) | DRF serializers / forms | built-in `CsrfViewMiddleware` | `DATA_UPLOAD_MAX_MEMORY_SIZE` |
| FastAPI / Starlette | `secure` package or a custom middleware | `CORSMiddleware(allow_origins=[...])` | `slowapi` (Redis) | Pydantic models (never `dict`) | `starlette-csrf` / `fastapi-csrf-protect` | proxy limit or a custom middleware |
| Flask | `flask-talisman` | `flask-cors` with origins | `Flask-Limiter` (Redis) | `marshmallow`/`pydantic` | `Flask-WTF` CSRFProtect | `MAX_CONTENT_LENGTH` |
| Spring Boot | Spring Security `headers()` (defaults on) | `CorsConfigurationSource` bean | `bucket4j` / API gateway | `@Valid` + Bean Validation | Spring Security CSRF (on by default) | `spring.servlet.multipart.max-*` |
| ASP.NET Core | `NWebsec` or custom middleware, `UseHsts()` | `AddCors` with named policy | built-in `AddRateLimiter` (.NET 7+) | DataAnnotations / FluentValidation | `[ValidateAntiForgeryToken]` | `MaxRequestBodySize` |
| Laravel | `bepsvpt/secure-headers` or middleware | `config/cors.php` | `throttle` middleware / `RateLimiter::for` | Form Requests | `VerifyCsrfToken` (web routes) | `post_max_size` / validation rules |
| Rails | `config.force_ssl`, `secure_headers` gem | `rack-cors` | `rack-attack` | strong parameters + model validations | `protect_from_forgery` | Rack/nginx limit |
| Go (gin/echo/chi/fiber) | `unrolled/secure`, echo `middleware.Secure`, fiber `helmet` | gin-contrib/cors, echo `CORSWithConfig`, `rs/cors` | `ulule/limiter`, `tollbooth`, fiber `limiter` | `go-playground/validator` | `gorilla/csrf` | `http.MaxBytesReader` |

Password hashing: bcrypt (`bcrypt`/`bcryptjs`, cost ≥ 10), argon2id (`argon2`, `argon2-cffi`),
scrypt; Django/Spring/ASP.NET/Laravel built-in hashers are fine. Tokens: `crypto.randomBytes`,
`secrets.token_urlsafe`, `SecureRandom`, `crypto/rand`.
