# SearchIntel AI Security

## Authentication and session configuration

The API uses FastAPI Users for account registration, password hashing, login, and logout. Set a unique `AUTH_SECRET` of at least 32 characters before using authentication. Generate one with `openssl rand -hex 32` and keep it only in the local environment or a secret manager; never commit it. `AUTH_COOKIE_SAMESITE` defaults to `strict`. Session cookies are HttpOnly; `Secure` defaults on when `APP_ENV=production` and can be explicitly controlled with `AUTH_COOKIE_SECURE`.

Cookie-authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests require the `searchintel_csrf` cookie value in `X-CSRF-Token`. The dashboard reads this non-HttpOnly CSRF token and sends it on writes. Do not disable this check for browser requests.

Sessions are opaque random tokens stored in Redis and expire after the configured `AUTH_TOKEN_LIFETIME_SECONDS` (default one hour). Logout deletes the server-side token as well as clearing the browser cookie, so a copied token stops working immediately. Authentication depends on Redis availability.

Redis-backed API throttles cover login, registration, crawl enqueue, and audit enqueue. Each bucket is keyed by the immediate peer address and operation category, so clients cannot bypass crawl/audit limits by varying website IDs. Defaults and windows are configurable with `AUTH_LOGIN_RATE_LIMIT`, `AUTH_LOGIN_RATE_WINDOW_SECONDS`, `AUTH_REGISTER_RATE_LIMIT`, `AUTH_REGISTER_RATE_WINDOW_SECONDS`, `CRAWL_ENQUEUE_RATE_LIMIT`, `CRAWL_ENQUEUE_RATE_WINDOW_SECONDS`, `AUDIT_ENQUEUE_RATE_LIMIT`, and `AUDIT_ENQUEUE_RATE_WINDOW_SECONDS`. Exceeding a limit returns `429` with `Retry-After`; when Redis is unavailable these endpoints fail closed with `503`. The application does not trust forwarded IP headers; deploy behind a correctly configured trusted-proxy boundary before using peer-IP throttles as an end-user identity control.

## Tenant access

Each registered user must have a `tenant_memberships` row for a tenant. Creating a tenant assigns its creator the `owner` role. Owners and admins can add already registered users as viewer, editor, or admin. Protected routes check membership before service access; write operations require editor or higher. Unauthorized tenant access deliberately returns 404.

Existing tenants are not automatically assigned to new accounts. Before enabling authentication against a database with legacy tenant data, run an explicit, reviewed membership backfill that maps known users to the correct tenants. Do not infer ownership from a client-supplied tenant ID.

`python -m app.cli audit-legacy-memberships` reports tenants with no memberships and their project/site counts. It is read-only and does not infer which user should own a tenant. Review its output against trusted ownership records before preparing membership changes.

Relational queries and vector retrieval retain tenant/project filters. Worker dispatch is only initiated after the authenticated API verifies the caller's membership and role; task payloads contain persisted job IDs, and workers resolve the tenant/project/site from the database.

## Remaining security work

- Project-level membership roles (current roles are tenant-level).
- Broader deployment security review and dependency/security scanning.
- A reviewed legacy membership backfill is required before exposing existing tenants to authenticated users.
- DNS pinning has controlled tests for a public-to-private rebinding change; do not treat those tests as a broad external security certification.

SQLite tests with a deterministic Redis test double verify anonymous rejection, cookie login/logout including replay rejection after logout, CSRF writes, membership isolation, and viewer/editor authorization. Disposable PostgreSQL 16 and Qdrant 1.12.6 integration tests exercised authenticated owner search, foreign project denial, and filtering of a mismatched-tenant vector. A separate PostgreSQL/Redis integration verified live session revocation. Playwright verifies browser login, tenant denial, and API failure paths. These checks do not establish production security.
