# SearchIntel AI

Agentic SEO, GEO, and content intelligence platform for crawling websites, processing their content, and powering evidence-backed search, RAG, competitor analysis, and SEO recommendations.

## Current State

The recovered backend includes persistent project, website, page, chunk, crawl-job, and SEO-audit models; Celery/Redis crawl and audit tasks; deterministic SEO findings; and BM25/vector hybrid retrieval with grounded RAG interfaces. The Next.js dashboard is connected to project, website, page, crawl, SEO, search, and RAG APIs.

Local checks pass for 40 backend tests, Ruff, mypy, Alembic, and frontend lint/typecheck/production build. A controlled integration used isolated PostgreSQL, Redis, and Qdrant containers plus a Celery solo worker to crawl a loopback fixture, persist/index pages, search and cite content, run an SEO audit, and render the results in the dashboard. Existing stopped `seo-*` containers and volumes were preserved. The host's Celery prefork pool failed under Python 3.14/macOS and remains an open deployment-runtime check. See `docs/PROGRESS.md` for details.

## Local Setup

```bash
cp .env.example .env
# Set unique POSTGRES_PASSWORD and NEO4J_PASSWORD values in .env first.
docker compose up -d postgres redis qdrant neo4j
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API docs are available at `http://localhost:8000/docs` when the backend is running.

In a second terminal, run the background worker from `backend/`:

```bash
uv run celery -A app.tasks.queue:celery_app worker --loglevel=INFO --queues=crawls,audits --pool=solo --concurrency=1
```

The solo pool is the verified local command for this host's Python 3.14/macOS runtime. Verify prefork against the target Linux/Python runtime before using it in production.

For the dashboard, run `npm install && npm run dev` from `frontend/`. It proxies `/api-proxy/*` to `http://127.0.0.1:8000` by default; set `SEARCHINTEL_API_ORIGIN` to override the API origin.

## Project Documents

- `docs/ARCHITECTURE.md` explains the system architecture and MVP sequencing.
- `docs/PROJECT_STATUS.md` tracks completed, active, and next work.
- `docs/decisions/` records architecture decisions.

## Security Notes

- Do not commit `.env` or secret values.
- URL validation blocks localhost, private networks, link-local ranges, and cloud metadata addresses by default.
- Tenant/project IDs are required in indexed chunks and retrieval filters.
