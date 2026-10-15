# SearchIntel AI project status

Updated: 2026-10-15

## Current checkpoint

- Recovery: complete. The 66-file available archive was restored without modifying the archive.
- Existing crawl-to-search and grounded RAG baseline: preserved; regression suite passes.
- Async crawl worker: implemented using Celery/Redis and persisted PostgreSQL jobs. A live solo worker recovered and completed a loopback crawl, wrote three pages and vectors, and returned progress. Prefork failed inside Celery's tracer on the host's Python 3.14/macOS runtime.
- Readiness endpoint: reports database, Redis, and a live Celery worker with `503` when not ready; unit checks and a live `200` check passed.
- Technical SEO audits: deterministic rules, relational persistence, Celery dispatch, tenant-scoped APIs, and audit history pass unit checks and a live audit (3 pages, 27 findings).
- Frontend: core Next.js dashboard implemented. Lint, typecheck, production build, dependency audit, and browser-backed rendering of live projects, pages, crawl state, and audit findings pass.
- Controlled integration: isolated PostgreSQL, Redis, and Qdrant containers completed migration, crawl, indexing, hybrid retrieval, grounded mock RAG, and SEO audit. Existing stopped `seo-*` containers and volumes were left untouched.
- Security boundary: tenant IDs scope rows but are not authenticated principals; do not expose this API as a multi-user service yet. External websites were not contacted.

## Verified checks

- `cd backend && uv sync --extra dev` — passed.
- `cd backend && uv run pytest -q` — 40 passed; one Starlette/httpx deprecation warning.
- `cd backend && uv run ruff check app tests` — passed.
- `cd backend && uv run mypy app` — passed (78 source files).
- `cd frontend && npm run lint`, `npm run typecheck`, and `npm run build` — passed.
- `cd frontend && npm audit` — passed; zero reported vulnerabilities.
- Browser workflow: loaded the live integration project, three persisted pages, completed crawl counters, and 27 audit findings after reload.
- SQLite Alembic upgrade — passed through `20261015_0002`.
- PostgreSQL Alembic upgrade — passed through `20261015_0002` against the isolated Docker service.
- Controlled live workflow: readiness, Redis/Celery worker, PostgreSQL pages, Qdrant vectors, hybrid search, grounded mock RAG with citation, SEO audit, and cross-tenant `404` passed against a loopback fixture.
- Celery dispatch is mocked in the unit suite; separate controlled integration did execute the worker and services. Prefork remains unverified because it crashed on this host; solo pool passed.

See [`docs/PROGRESS.md`](PROGRESS.md), [`docs/MVP_ROADMAP.md`](MVP_ROADMAP.md), and [`PROJECT_STATE.json`](../PROJECT_STATE.json) for the checkpoint and next work.
