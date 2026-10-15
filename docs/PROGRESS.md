# SearchIntel AI development progress

Updated: 2026-10-15

## Verified checkpoint

The recovered backend now has locally verified asynchronous crawling, deterministic SEO audits, and a connected Next.js dashboard. A controlled end-to-end workflow ran against isolated PostgreSQL, Redis, Qdrant, a real Celery solo worker, FastAPI, and a loopback-only fixture website. Previously stopped `seo-*` containers and their volumes were inspected and left untouched.

| Workstream | Status | Evidence |
|---|---|---|
| Recovery | Complete | 66 archive files restored and hash checked; see `RECOVERY_REPORT.md`. |
| Baseline backend | Local checks pass | Existing crawl-to-search/RAG interfaces preserved; full suite now 40 tests. |
| Async crawling | Implemented; live local worker verified | Celery consumed Redis tasks, recovered a pending job after worker restart, crawled the fixture, tracked counters, and persisted three pages. Solo pool used; prefork crashed in this host's Python 3.14/Celery runtime. |
| Technical SEO | Implemented; live local service verified | A worker audited three PostgreSQL pages and persisted 27 findings; status, history, summary, and finding APIs returned the stored results. |
| Frontend | Implemented; live API workflows browser-verified | Dashboard loaded persisted pages, crawl history, and all 27 audit findings for the selected live project/site. Project/website creation was also browser-tested. Tenant and latest-run restoration are implemented through browser storage and history APIs. |
| Live service E2E | Controlled stack passed | Isolated Docker Compose project with PostgreSQL, Redis, and Qdrant. Existing `seo-*` containers and volumes were preserved. |

## Implementation details

- Crawl `POST /api/v1/websites/{website_id}/crawl` persists and queues a job, returning `202` without waiting for the crawl.
- `GET /api/v1/crawl-jobs/{job_id}` includes discovered, queued, processed, successful, and failed counters; `DELETE` requests safe cancellation.
- A Celery worker runs `searchintel.execute_crawl` and `searchintel.execute_audit`; transient HTTP failures retry with bounded exponential delays. Worker startup requeues pending and stale jobs.
- Crawling preserves PostgreSQL page/chunk persistence and content-hash-based indexing skips. Scope is same-host, depth/page/concurrency bounded, paced, robots-aware, and revalidated on redirects.
- SEO audits analyze persisted crawl pages, robots.txt, sitemap XML, and findings; audit endpoints are under `/api/v1/seo-audits` and `/api/v1/websites/{website_id}/seo-audits`.
- Indexability findings explicitly state that HTML signals do not establish search-engine indexing.
- The dashboard uses the real project, website, page, crawl, SEO, search, and RAG APIs; it supports project/website creation, crawl progress and cancellation, audit filtering, page browsing, search, and citation display. Tenant identity remains a local-development input because authentication is not implemented.
- HTTP response bodies now stream with a configurable 5 MB default size limit (maximum configurable value 50 MB); a controlled test verifies oversized bodies fail before full buffering.
- `/api/v1/health/ready` reports database, Redis, and responding Celery workers separately and returns HTTP 503 until all three are available; behavior is covered with mocked dependencies.
- Tenant-scoped website history endpoints list up to 20 crawl jobs and audits; the dashboard reads latest crawl/audit/findings from those persisted endpoints and stores tenant selection in browser storage.

## Latest checks actually run

- `cd backend && uv sync --extra dev`: passed; Celery/Redis client dependencies installed into the project virtual environment.
- `cd backend && DATABASE_URL=sqlite:////tmp/searchintel-migration-verify-20261015.db uv run alembic upgrade head`: passed through `20261015_0002`.
- `cd frontend && npm run lint`: passed (Biome; 3 checked files).
- `cd frontend && npm run typecheck`: passed.
- `cd frontend && npm run build`: passed with Next.js 16.4.1.
- `cd frontend && npm audit`: passed; zero reported vulnerabilities.
- Browser smoke test against `http://127.0.0.1:3000` and FastAPI on port 8000: created a project and registered `https://example.com` in a disposable SQLite DB; dashboard reflected both API-backed records. No external website crawl was initiated.
- `cd backend && uv run pytest -q`: **40 passed**, one Starlette/httpx TestClient deprecation warning after adding readiness/history coverage.
- `cd backend && uv run ruff check app tests`: passed after history endpoints and worker fixes.
- `cd backend && uv run mypy app`: passed for 78 source files after history endpoints and worker fixes.
- Docker was started and a fresh isolated `searchintel-verify` project ran PostgreSQL, Redis, and Qdrant; the pre-existing `seo-*` containers and named volumes were not modified. The verification containers are now stopped and their new test-only volumes were retained.
- PostgreSQL Alembic upgrade passed through `20261015_0002` against the isolated Docker PostgreSQL database.
- Live readiness returned `200` with database, Redis, and a responding Celery worker.
- Live crawl/audit/search/RAG: three loopback fixture pages persisted to PostgreSQL, three vectors counted in Qdrant, hybrid search returned three results, grounded RAG returned one citation using the mock LLM, and the SEO audit stored 27 findings. Cross-tenant project lookup returned `404`.
- Browser loaded persisted project/site/page data, a completed crawl and counters, and all 27 findings through the API. Tenant/localStorage reload behavior is implemented but was not separately exercised after the final browser build.
- The first prefork worker attempt crashed inside Celery's fast task tracer on this Python 3.14/macOS host. Verification succeeded using `--pool=solo --concurrency=1`; prefork remains an open runtime check.
- Live setup caught and fixed `ProjectService` ignoring configured `ALLOW_LOCAL_URLS`; a regression test covers explicitly permitted loopback website registration.

## Known gaps and next actions

1. Resolve and verify the Celery prefork runtime on the target Python version; this live check used Celery's solo pool.
2. Add authenticated tenant membership and authorization; tenant IDs scope data but are not authenticated identities, so this is not ready for multi-user deployment.
3. Add committed browser E2E automation, retry/cancellation/crash-recovery service tests, and performance/resource benchmarks.
4. Continue the master roadmap with competitor analysis, recommendations, monitoring, GEO, and deployment/research work; these are not implemented by this checkpoint.

Git remains a damaged recovered checkout with no configured remote and missing objects reported by `git fsck`; no commit or history rewrite was made.
