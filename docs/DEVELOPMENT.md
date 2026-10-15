# Local development

## Configuration

Copy `.env.example` to `.env` and set a strong unique `AUTH_SECRET` (`openssl rand -hex 32`). Configure PostgreSQL, Redis, Qdrant, and other services as needed. Local HTTP uses non-Secure cookies by default; production sets Secure cookies automatically when `APP_ENV=production`.

Install backend dependencies from the lock file with `cd backend && uv sync --extra dev`. Apply relational migrations with `cd backend && uv run alembic upgrade head`. Start FastAPI and a Celery worker in separate terminals; on macOS/Python 3.14 use the existing `--pool=solo --concurrency=1` fallback. Linux/Python 3.12 prefork has a separate controlled verification record in `docs/PROGRESS.md`.

Install frontend dependencies with `cd frontend && npm ci`; run the dashboard with `npm run dev`. The Next.js same-origin `/api-proxy` rewrite forwards requests to `SEARCHINTEL_API_ORIGIN` (default `http://127.0.0.1:8000`).

## Checks

- `cd backend && uv run pytest -q`
- `cd backend && uv run ruff check app tests`
- `cd backend && uv run mypy app`
- `cd frontend && npm run lint && npm run typecheck && npm run build`

## Read-only legacy membership audit

After configuring a reachable project database and applying migrations, run `cd backend && uv run python -m app.cli audit-legacy-memberships --format json` (or `--format csv`). The command reports tenants and project/site/membership counts; it does not infer ownership or write memberships. SQLite is opened in read-only mode and PostgreSQL runs a read-only transaction. Review trusted user-to-tenant mappings before preparing any backfill.

Use test fixtures and controlled local services. Do not crawl external websites or make paid model calls from tests.
