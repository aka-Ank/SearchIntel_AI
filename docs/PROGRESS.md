# SearchIntel AI development progress

Updated: 2026-10-18

## 2026-10-18 — Authorized local SQLite orphan repair

- Created and independently verified `backend/backups/searchintel.pre-orphan-repair-20261018.db` before changing the working database. The backup is an 81,920-byte SQLite snapshot with `integrity_check=ok` and preserves the original one page, one content chunk, and foreign-key violation.
- With the user's explicit approval, deleted exactly the orphan page row and its one dependent content chunk from ignored `backend/searchintel.db`. No tenant, project, or website rows existed, and no other rows were changed.
- Reopened and validated the working database: `integrity_check=ok`, zero `foreign_key_check` violations, and zero rows in tenants, projects, websites, pages, and content_chunks. The original remains recoverable from the verified backup.
- No schema migration was run. The separate legacy Alembic adoption issue remains: plain upgrade against the unstamped legacy schema fails because the baseline `tenants` table already exists; the migration rehearsal was performed on a disposable copy only.

## Verified checkpoint

The recovered backend has verified asynchronous crawling, deterministic SEO audits, authenticated tenant access, configured-provider support, competitor coverage, and a connected Next.js dashboard. The controlled crawl/search/RAG/SEO workflow ran against isolated PostgreSQL, Redis, Qdrant, Celery, FastAPI, and loopback fixtures. The damaged original Git metadata and recovered files remain preserved; a clean local snapshot repository holds project history.

| Workstream | Status | Evidence |
|---|---|---|
| Recovery | Complete | 66 archive files restored and hash checked; see `RECOVERY_REPORT.md`. |
| Baseline backend | Local checks pass | Existing crawl-to-search/RAG interfaces preserved; latest suite is 61 passed and three opt-in PostgreSQL/Qdrant checks skipped without their service URLs. |
| Async crawling | Implemented; solo and Linux prefork verified | Celery recovered jobs, tracked progress, and persisted pages. A full Python 3.12 prefork workflow crawled two pages, indexed vectors, searched, answered with a citation, and completed an SEO audit. macOS/Python 3.14 development retains the solo pool. |
| Technical SEO | Implemented; live local service verified | A worker audited three PostgreSQL pages and persisted 27 findings; status, history, summary, and finding APIs returned the stored results. |
| Frontend | Implemented; browser E2E passed | Playwright verifies auth, tenant isolation, project and website creation, crawl progress, audit findings, indexed pages, cited mock RAG, competitor crawling/coverage, and API failure display. |
| Live service E2E | Controlled stack passed | Isolated Docker Compose project with PostgreSQL, Redis, and Qdrant. Existing `seo-*` containers and volumes were preserved. |
| Authentication | Implemented; SQLite and PostgreSQL checks passed | FastAPI Users, CSRF, tenant roles, Alembic `20261015_0003`, and PostgreSQL cross-tenant denial verified. |
| API rate limiting | Implemented; deterministic and Redis-backed E2E verified | Login, registration, crawl enqueue, and audit enqueue use configurable Redis counters. The local Playwright suite exceeded the login threshold and observed `429` with `Retry-After`. |
| PostgreSQL/Qdrant tenant isolation | Authenticated API integration passed | Fresh PostgreSQL 16 and Qdrant 1.12.6 services ran authenticated search: the owner retrieved their vector, an outsider received `404` on the foreign project, and an intentionally mismatched-tenant vector sharing the outsider's project ID was filtered out. Redis sessions used the test double; live Redis session revocation was verified separately. |
| Crawler DNS pinning | Implemented; controlled rebinding tests and browser crawl passed | The socket transport resolves and validates answers immediately before connecting to a selected IP, while retaining the original host for HTTP and TLS. Ambient proxy settings are disabled for crawler fetches. |
| Legacy membership audit | Read-only command implemented and fixture-tested | `python -m app.cli audit-legacy-memberships` reports tenant, project, website, and membership counts. SQLite opens read-only and PostgreSQL starts a read-only transaction; it does not infer owners or write rows. The configured project PostgreSQL was unreachable at `localhost:5432`, so project data was not audited. |
| Worker reliability | Service tests and full Linux prefork workflow passed | Retry, stale recovery, idempotency, cancellation, and failure persistence tests pass; prefork completed crawl through audit. |
| LLM provider | Adapter implemented; mock tests passed | OpenAI-compatible provider has bounded retries/timeouts, usage accounting, and optional cost estimates. No live provider call was made. |
| Competitor intelligence | Evidence-linked content-gap review in browser | Competitors use the existing crawl/index flow. Candidate phrases show exact/semantic match method, pages observed, and source links. Competitor-only candidates prompt a human to review fit; they do not imply demand or a publish recommendation. |

## Implementation details

- Crawl `POST /api/v1/websites/{website_id}/crawl` persists and queues a job, returning `202` without waiting for the crawl.
- `GET /api/v1/crawl-jobs/{job_id}` includes discovered, queued, processed, successful, and failed counters; `DELETE` requests safe cancellation.
- A Celery worker runs `searchintel.execute_crawl` and `searchintel.execute_audit`; transient HTTP failures retry with bounded exponential delays. Worker startup requeues pending and stale jobs.
- Crawling preserves PostgreSQL page/chunk persistence and content-hash-based indexing skips. Scope is same-host, depth/page/concurrency bounded, paced, robots-aware, and revalidated on redirects.
- SEO audits analyze persisted crawl pages, robots.txt, sitemap XML, and findings; audit endpoints are under `/api/v1/seo-audits` and `/api/v1/websites/{website_id}/seo-audits`.
- Indexability findings explicitly state that HTML signals do not establish search-engine indexing.
- The dashboard uses the real project, website, page, crawl, SEO, search, and RAG APIs; it supports project/website creation, crawl progress and cancellation, audit filtering, page browsing, search, and citation display. The dashboard previously accepted a local tenant ID; the 2026-10-15 auth slice replaces that with login, CSRF-protected writes, and membership-scoped workspace selection.
- HTTP response bodies now stream with a configurable 5 MB default size limit (maximum configurable value 50 MB); a controlled test verifies oversized bodies fail before full buffering.
- `/api/v1/health/ready` reports database, Redis, and responding Celery workers separately and returns HTTP 503 until all three are available; behavior is covered with mocked dependencies.
- Tenant-scoped website history endpoints list up to 20 crawl jobs and audits; the dashboard reads latest crawl/audit/findings from those persisted endpoints and stores tenant selection in browser storage.
- Redis Lua counters apply configurable IP/category rate limits to login, registration, crawl enqueue, and audit enqueue. They return `429` plus `Retry-After`, and fail closed with `503` when Redis is unavailable. Forwarded IP headers are not trusted.
- Competitor-only phrase candidates include evidence links, observed page counts, match method, and a review prompt. The dashboard labels exact/semantic comparison and makes clear that competitor coverage does not establish demand or justify publication.

## Earlier controlled-service checkpoint checks

- `cd backend && uv sync --extra dev`: passed; Celery/Redis client dependencies installed into the project virtual environment.
- `cd backend && DATABASE_URL=sqlite:////tmp/searchintel-auth-migration-final-20261015.db uv run alembic upgrade head`: passed through `20261015_0003`.
- `cd frontend && npm run lint && npm run typecheck && npm run build`: latest run passes with Biome checking 8 files and Next.js 16.4.1.
- `cd frontend && npm audit`: passed; zero reported vulnerabilities.
- Browser smoke test against `http://127.0.0.1:3000` and FastAPI on port 8000: created a project and registered `https://example.com` in a disposable SQLite DB; dashboard reflected both API-backed records. No external website crawl was initiated.
- `cd backend && uv run pytest -q`: **52 passed**, one Starlette/httpx TestClient deprecation warning.
- `cd backend && uv run ruff check app tests`: passed.
- `cd backend && uv run mypy app`: passed for 85 source files.
- Docker was started and a fresh isolated `searchintel-verify` project ran PostgreSQL, Redis, and Qdrant; the pre-existing `seo-*` containers and named volumes were not modified. The verification containers are now stopped and their new test-only volumes were retained.
- PostgreSQL Alembic upgrade passed through `20261015_0002` against the isolated Docker PostgreSQL database.
- Live readiness returned `200` with database, Redis, and a responding Celery worker.
- Live crawl/audit/search/RAG: three loopback fixture pages persisted to PostgreSQL, three vectors counted in Qdrant, hybrid search returned three results, grounded RAG returned one citation using the mock LLM, and the SEO audit stored 27 findings. Cross-tenant project lookup returned `404`.
- Browser loaded persisted project/site/page data, a completed crawl and counters, and all 27 findings through the API. Tenant/localStorage reload behavior is implemented but was not separately exercised after the final browser build.
- The first prefork worker attempt crashed inside Celery's fast task tracer on this Python 3.14/macOS host. Verification succeeded using `--pool=solo --concurrency=1`; prefork remains an open runtime check.
- Live setup caught and fixed `ProjectService` ignoring configured `ALLOW_LOCAL_URLS`; a regression test covers explicitly permitted loopback website registration.

## 2026-10-15 — Redis-backed API rate-limit checkpoint

- Added validated environment settings for login, registration, crawl enqueue, and audit enqueue limits/windows. The atomic Redis Lua counter keys by immediate peer address and operation category, not website ID; excess requests receive `429` and `Retry-After`, while Redis failure returns `503`.
- Added deterministic unit coverage for registration throttling and fail-closed Redis outages, plus a Playwright live-Redis check that sends invalid login requests until the configured threshold is reached. Updated `.env.example` and `docs/SECURITY.md` with defaults and proxy trust boundaries.
- Verification: `cd backend && uv run pytest -q` — **54 passed** (one existing Starlette/httpx TestClient deprecation warning); Ruff passed; mypy passed for 86 source files. `cd frontend && npm run lint && npm run typecheck` passed. `cd frontend && npm run e2e:local` — **3 passed**, including actual Redis throttling.
- No database migration was needed. Rate limiting is now verified locally; no claims are made about production proxy configuration or distributed deployment behavior beyond Redis atomicity.

## 2026-10-15 — Qdrant tenant-filter integration

- Added an opt-in integration test that creates a unique temporary collection, indexes two tenant-owned chunks with colliding project and website IDs, checks each tenant-filtered vector query returns only its own chunk, and deletes the collection.
- Executed against a fresh isolated `qdrant/qdrant:v1.12.6` container: **1 passed**. The test-owned container was removed; normal backend tests do not require Qdrant and report this test skipped unless `SEARCHINTEL_TEST_QDRANT_URL` is configured.
- This focused check validates Qdrant payload filtering at the vector-store layer; the authenticated PostgreSQL/Qdrant request path is verified in the following checkpoint.

## 2026-10-15 — Authenticated PostgreSQL-to-Qdrant isolation

- Added an opt-in API integration test that registers two users, creates separate tenants/projects, indexes vectors into a unique Qdrant collection, and searches through authenticated FastAPI routes backed by PostgreSQL.
- The test verifies owner retrieval, cross-tenant project access denial (`404`), and filtering of a deliberately mismatched-tenant vector whose project ID matches the second tenant's project.
- Executed against fresh PostgreSQL 16 and Qdrant 1.12.6 containers: migrations through `20261015_0003` passed and both Qdrant integration tests passed. Authentication session storage used the deterministic Redis test double in this run; separate isolated PostgreSQL/Redis tests verified session persistence and logout revocation. All test-owned containers were removed.

## 2026-10-15 — Read-only legacy membership audit

- Added `python -m app.cli audit-legacy-memberships [--format json|csv]`. It reports tenant IDs/names and project, website, and membership counts, highlighting tenants with no memberships without guessing an owner or assigning anyone.
- SQLite access uses `mode=ro` and refuses a missing database file. PostgreSQL starts a read-only transaction. Fixture tests verify counts, no row changes, and no creation of a missing SQLite file.
- `cd backend && uv run pytest -q`: **61 passed, 3 skipped** (opt-in PostgreSQL/Qdrant integrations and PostgreSQL audit integration without service URLs); Ruff passed; mypy passed for 89 source files; `uv lock --check` passed.
- A separate opt-in PostgreSQL test passed against a fresh PostgreSQL 16 container after Alembic upgrade through `20261015_0003`. It verified the read-only audit transaction and temporary fixture reporting; the container was removed afterward. This was not the configured project database.
- Attempted the audit against the configured project database; the `.env` points to PostgreSQL on `localhost:5432`, where the connection was refused. No project tenant data was read or changed. Re-run when PostgreSQL is available, then review known user-to-tenant mappings before any backfill.

## 2026-10-15 — Competitor gap review UX

- Competitor-only phrase findings now include an evidence-based review action; shared topics omit the action. The dashboard shows the match method, number of crawled competitor pages, all returned evidence links, and the review prompt.
- The prompt explicitly says that competitor coverage alone does not establish demand or justify publication. The candidate extraction remains deterministic, with optional sentence-transformer similarity and no ranking/traffic metrics.
- Verification: backend **61 passed, 3 opt-in database tests skipped** in the no-service run, Ruff and mypy passed; frontend lint/typecheck/build passed; `cd frontend && npm run e2e:local` **3 passed**, including the competitor review prompt.

## 2026-10-15 — Competitor phrase evidence boundaries

- Evidence matching now checks phrase token boundaries, avoiding false matches where a candidate appears only inside a longer word. Evidence snippets use the same match location.
- Verification: `tests/test_competitor_intelligence.py` **2 passed**; full backend suite **61 passed, 3 skipped**; Ruff, mypy, and all **3 Playwright E2E** tests passed.
- Semantic similarity was not executed: the optional `sentence-transformers` package and configured model weights are absent locally. No model download was attempted.

## 2026-10-15 — Competitor extraction microbenchmark

- Added `backend/scripts/profile_competitor_topics.py` for a repeatable synthetic profile: `cd backend && uv run python -m scripts.profile_competitor_topics`.
- On Python 3.14.6, 1,000 synthetic pages with 875 words each (875,000 total) produced 95 distinct candidates in 3.076 seconds with 0.12 MiB traced peak allocation on the latest run.
- This measures `_topic_counts` only and excludes database access, semantic embeddings, crawling, indexing, and frontend work. It is a bounded component check, not a whole-service throughput or production capacity claim. Full crawl-to-search resource profiling remains pending.

## 2026-10-18 — Repository integrity recheck

- `git fsck --full --no-reflogs` completed without errors. All 165 tracked paths exist, and the working tree had no tracked modifications before this recheck.
- `backend/searchintel.db` was inspected read-only; SQLite returned `integrity_check=ok` and has six legacy application tables. The `.env` and database remain ignored and are not tracked.
- The SQLite file contains one page and one chunk but no tenant, project, or website parents; `PRAGMA foreign_key_check` reports one page-to-website violation. I preserved it rather than delete the content or invent missing ownership records.
- A disposable backup rehearsal showed raw `alembic upgrade head` stops because the existing `tenants` table predates Alembic stamping. Stamping the verified baseline `20261003_0001` on the copy then upgrading reached `20261015_0003`; the foreign-key violation remained. The source file was not modified.
- The choice to preserve that SQLite data and require trusted parent records or explicit pruning approval is documented in [ADR 006](decisions/006-preserve-legacy-sqlite-data.md).
- Preserved the existing generated `.playwright-mcp/` console log and added the directory to `.gitignore` to prevent accidental commits.
- Backend verification rerun: **61 passed, 3 skipped**, Ruff passed across app/tests/scripts, mypy passed for 89 source files, and `uv lock --check` passed. Frontend lint, typecheck, and production build passed.
- The latest Playwright rerun could not start because the Docker daemon socket was absent. The last successful 3-test browser run remains the 2026-10-15 result; current E2E verification is pending Docker availability.

## 2026-10-15 — Crawler DNS pinning

- Added a pinned HTTPX transport backed by httpcore. At socket-open time it resolves the destination again, rejects unsafe answers, and connects directly to the selected vetted IP; the URL hostname remains unchanged for the HTTP `Host` header and TLS SNI. Environment proxy variables are not honored by the crawler transport.
- Validation covered a controlled HTTP server reached through a test hostname, preservation of the original `Host`, a simulated public-to-private DNS change rejected before connection, the full backend suite, and the Playwright crawl/audit/RAG flow.
- `cd backend && uv run pytest -q`: **58 passed, 2 skipped** (opt-in PostgreSQL/Qdrant integrations without service URLs); Ruff passed; mypy passed for 87 source files; `uv lock --check` passed. `cd frontend && npm run lint && npm run typecheck` passed; `cd frontend && npm run e2e:local`: **3 passed**.
- No external website was crawled. The rebinding test uses controlled resolver answers, so this establishes the transport behavior under the tested cases rather than a broad external security certification.

## Historical first checkpoint gaps (superseded by the verified updates below)

1. Resolve and verify the Celery prefork runtime on the target Python version; this live check used Celery's solo pool.
2. Verify the new authenticated tenant membership and authorization against PostgreSQL and browser E2E; plan explicit membership backfill for existing tenants.
3. Add committed browser E2E automation, retry/cancellation/crash-recovery service tests, and performance/resource benchmarks.
4. Continue the master roadmap with competitor analysis, recommendations, monitoring, GEO, and deployment/research work; these are not implemented by this checkpoint.

Historical checkpoint note: this entry predates the 2026-10-15 repository preservation and authentication update below.

## 2026-10-15 — Repository checkpoint and authentication slice

- Preserved the pre-existing worktree and original Git metadata under `/tmp/searchintel-preserve-20261015/`. The original object database still reports seven missing blobs and has no configured remote; no objects were rewritten or fabricated. A separate clean local repository now records the recovered working tree at commit `e4cf581` (`chore: checkpoint recovered SearchIntel project snapshot`). `.env` remains ignored; machine-local Claude permission settings are excluded.
- Added FastAPI Users 14 with its SQLAlchemy adapter, password hashing, opaque Redis-backed session cookies, configurable secret, HttpOnly/SameSite cookie flags, and CSRF double-submit protection for cookie-authenticated writes. Logout revokes the Redis token. New `/api/v1/auth/*` routes cover registration, login, logout, and current-user lookup.
- Added relational `users` and `tenant_memberships` tables in Alembic revision `20261015_0003`; `/api/v1/tenants` creates an owner membership and lists only the caller's tenants. Admin/owner members can list or add existing users with viewer/editor/admin roles.
- Required tenant membership and minimum role checks on project, website, crawl, audit, indexing, page, search, and RAG endpoints. Cross-tenant requests return 404. The dashboard now has login/registration, session restore, authorized tenant selection, and CSRF headers.
- Tests cover anonymous rejection, cookie login/logout, CSRF, cross-tenant denial, and viewer/editor roles. Full backend suite: **43 passed**; Ruff and mypy pass. Fresh SQLite migration passes through `20261015_0003`. Frontend lint, typecheck, and production build pass.
- Auth migration has not yet been run against PostgreSQL, and browser E2E has not yet exercised the new login UI. Existing project and website data require explicit membership backfill before those users can access them; current API does not silently assign legacy tenants to new accounts.
- Current next task: complete an isolated Celery prefork check on Linux/Python 3.12 and strengthen service-level retry, recovery, cancellation, idempotency, and failure-state tests. A no-credential real LLM adapter and Playwright browser suite follow; paid/live provider smoke remains unverified.
- Initial Linux/Python 3.12.15 prefork probe verified worker ping and routed task delivery using an absent job ID. A later full prefork crawl/search/RAG/audit run is recorded in the current checkpoint below.
- Added `docs/SECURITY.md` and `docs/DEVELOPMENT.md` for secret setup, cookie/CSRF behavior, role policy, legacy tenant backfill requirements, and current security limits.

## 2026-10-15 — Verified authentication, provider, browser, and competitor checkpoint

- PostgreSQL 16 migration through `20261015_0003` passed. Registration, login, tenant/membership persistence, tenant-local project access, cross-tenant `404`, and logout token replay rejection were exercised against isolated PostgreSQL and Redis containers. This probe caught and fixed tenant/membership insert ordering.
- Backend checks: **52 passed**, Ruff passed, and mypy passed for 85 source files. SQLite migration passed through `20261015_0003`.
- Linux/Python 3.12 prefork worker startup, control ping, and routed task delivery passed on an isolated Docker network. An additional full run then verified prefork crawl, PostgreSQL page persistence, Qdrant vector count, hybrid search, cited mock RAG, and SEO audit against isolated PostgreSQL/Redis/Qdrant and a fixture server. Two fixture pages were persisted and indexed.
- Redis-backed opaque session tokens are deleted on logout; an isolated PostgreSQL/Redis integration replayed the old cookie and received `401`.
- `npm run e2e:local`: **2 Playwright tests passed** against isolated SQLite, Redis, a solo Celery worker, FastAPI, Next.js, and local HTML fixtures. E2E covered signup, tenant isolation, project/site creation, crawl, SEO audit, page explorer, citation display, competitor registration/crawl/topic coverage, and API failure UI. This harness does not use PostgreSQL or Qdrant.
- `OpenAICompatibleProvider` includes environment credentials, configurable model/base URL, bounded timeouts/retries, usage and optional cost accounting, and citation-grounded requests. Mock tests pass; no real provider call was made. Streaming remains unimplemented.
- Competitor comparison is evidence-backed and tenant-scoped. Phrase extraction is deterministic; sentence-transformer configuration enables semantic similarity matching. The default deterministic embedding provider does not claim semantic equivalence, and no live embedding model was run in this checkpoint.

## Remaining work

- Run the read-only membership audit when PostgreSQL is available; review explicit ownership mappings before any backfill and profile resource usage.
- A live LLM smoke test and streaming need configured credentials and explicit paid-inference authorization.
- Extend semantic competitor topic quality and comparative technical SEO audits. No ranking, traffic, backlink, or keyword-demand claims are made.
