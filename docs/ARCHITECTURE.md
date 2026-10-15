# SearchIntel AI Architecture

## Product Boundary

SearchIntel AI is a multi-tenant platform for website crawling, semantic content understanding, hybrid retrieval, citation-based RAG, competitor intelligence, and SEO/GEO recommendations. The verified core MVP is the crawl-to-evidence vertical slice plus a connected local dashboard. Authentication, production worker runtime, and advanced intelligence remain pending.

## System Components

### API Layer

FastAPI exposes versioned endpoints under `/api/v1`. API handlers validate requests and delegate work to services. They do not contain crawler, retrieval, NLP, graph, or scoring logic.

Endpoint groups:

- `/api/v1/health` (process liveness)
- `/api/v1/health/ready` (database, Redis, Celery worker readiness)
- `/api/v1/projects`
- `/api/v1/projects/{project_id}/websites`
- `/api/v1/websites/{website_id}/crawl`
- `/api/v1/websites/{website_id}/crawl-jobs` (tenant-scoped history)
- `/api/v1/crawl-jobs/{job_id}`
- `DELETE /api/v1/crawl-jobs/{job_id}`
- `/api/v1/websites/{website_id}/seo-audits`
- `GET /api/v1/websites/{website_id}/seo-audits` (tenant-scoped history)
- `/api/v1/seo-audits/{audit_run_id}` (findings, summary)
- `/api/v1/pages/{page_id}/seo-findings`
- `/api/v1/projects/{project_id}/pages`
- `/api/v1/pages/{page_id}`
- `/api/v1/search`
- `/api/v1/rag/query`
- legacy/local fixture indexing remains available at `/api/v1/index/url`
- planned: competitors, content gaps, internal links, graph workflows, and broader dashboard views

### Frontend Dashboard

`frontend/` contains a Next.js App Router client dashboard using TypeScript and Tailwind CSS. It routes requests through a same-origin proxy to the versioned FastAPI API and reads persisted project, website, page, crawl, and audit data. It also submits hybrid-search and grounded-RAG questions and displays citations returned by the API. The current local workspace takes a tenant ID as user input; this is not authentication or authorization and must be replaced before multi-user deployment.

### Service Layer

Services coordinate implemented use cases:

- project creation
- crawl and index workflow
- asynchronous crawl and audit jobs
- deterministic SEO audits
- hybrid retrieval and grounded RAG
- planned: content gaps, internal link recommendations, and broader evaluation

Services accept explicit tenant and project context. Every content item and search filter carries tenant/project IDs.

### Crawler

The crawler is split into:

- URL normalization and safety validation
- fetcher interface
- HTTP fetcher implementation
- HTML parser
- crawl orchestration

HTTP response bodies are read in bounded streaming mode, controlled by `CRAWLER_MAX_RESPONSE_BYTES` (5 MB by default, maximum 50 MB). Oversized content is treated as a failed page rather than retained fully in process memory.

The crawler supports bounded multi-page crawls with max-page and max-depth limits, same-host confinement, URL safety validation at each redirect, duplicate prevention, content-type filtering, configurable per-job concurrency, request pacing, and robots.txt restrictions. HTTP transient failures receive bounded exponential retries. Crawl jobs and audit runs are dispatched through Celery over Redis, with PostgreSQL as the job-state authority. Cancellation is cooperative between crawl batches and page indexing operations. Worker startup requeues pending and stale jobs.

### Processing Pipeline

The processing pipeline converts HTML into normalized page content:

1. parse metadata, headings, links, and body text
2. clean boilerplate and non-content elements
3. chunk by document structure, not blind fixed character splitting
4. compute content hash
5. generate embeddings
6. index chunks into retrieval stores

### Retrieval

The retrieval stack has independent providers:

- dense vector search
- BM25 lexical search
- Reciprocal Rank Fusion
- reranker interface

The MVP keeps deterministic local embeddings so tests and demos do not require external keys or model downloads. A sentence-transformers provider supports local production use with `BAAI/bge-small-en-v1.5` by configuration. Qdrant is the production/default vector store when configured, and the in-memory vector store remains for fast offline tests. Cross-encoder reranking is available behind a `Reranker` interface, with `NoOpReranker` as the offline default.

### RAG

RAG uses retrieval results as explicitly untrusted content. Prompts separate system instructions from retrieved webpage text. Grounded mode answers only from supplied evidence and returns validated citations with URL, title, page ID, chunk ID, heading path, and snippet. The core implementation uses an `LLMProvider` abstraction with `MockLLMProvider` for offline tests.

### Storage

The production persistence target is PostgreSQL with SQLAlchemy and Alembic for relational entities:

- Tenant
- Project
- Website
- Competitor
- Page
- PageSnapshot
- ContentChunk
- Entity
- Topic
- Link
- Keyword
- CrawlJob
- AnalysisJob
- RAGQuery
- RetrievedChunk
- EvaluationResult

PostgreSQL stores projects, websites, pages, chunks, crawl jobs, SEO audit runs, and findings through SQLAlchemy and Alembic migrations. Qdrant stores chunk vectors with payload filters for tenant, project, website, and page IDs. Redis is the Celery broker and result backend. Neo4j is reserved for graph queries once the crawl/content model is stable.

### Multi-Tenancy

Tenant isolation is enforced at every boundary:

- API requests include tenant context.
- Database rows include tenant ID and project ID where applicable.
- Vector payloads include tenant/project filters.
- Retrieval services always filter by tenant/project.
- Tests prove tenant A cannot retrieve tenant B content.

### Observability

Structured logs include request ID, tenant ID, project ID, crawl job ID, and timing for crawling, embedding, retrieval, reranking, and LLM calls. Secret values must never be logged.

`/api/v1/health/ready` performs bounded checks for database connectivity, Redis broker reachability, and at least one responding Celery worker. It returns `503` when any dependency is unavailable; liveness remains separately exposed at `/api/v1/health`.

## Persistent Crawl-To-Search Flow

```text
Website
  -> bounded crawler
  -> parser / content normalization
  -> PostgreSQL Page
  -> structure-aware chunks
  -> PostgreSQL ContentChunk
  -> embedding provider
  -> Qdrant point payloads

Query
  -> query processor
  -> BM25 rebuilt from persisted chunks
  -> Qdrant dense retrieval with embedding-version filters
  -> Reciprocal Rank Fusion
  -> optional cross-encoder reranker
  -> source URL / chunk search results
```

If a page content hash is unchanged, the pipeline updates crawl metadata but skips chunk replacement, embedding, and vector replacement.

Embedding model changes are handled by versioned Qdrant collection names plus embedding metadata in point payloads. The maintenance CLI can reindex persisted chunks into the currently configured vector collection.

## Grounded RAG Flow

```text
Question
  -> retrieval strategy: bm25 | dense | hybrid | hybrid_rerank
  -> context builder with stable citation numbers
  -> grounded prompt
  -> LLM provider
  -> citation validation / repair
  -> structured answer with citations
```

Retrieved webpage text is treated as untrusted evidence, not instructions.

## First Vertical Slice

The first production slice is:

```text
Website URL
  -> safe URL validation
  -> fetch HTML
  -> parse page metadata and text
  -> structure-aware chunks
  -> deterministic embedding provider
  -> vector and BM25 indexes
  -> hybrid search API
  -> retrieved results with source metadata
```

This flow has passed unit checks and a controlled PostgreSQL/Redis/Celery/Qdrant integration against a loopback fixture. Deterministic embeddings and a mock LLM remain the offline defaults; external model quality and production deployment are not verified.

## MVP Milestones

1. Local crawl-to-search/RAG foundation — implemented and regression-tested.
2. PostgreSQL models and Alembic migrations — SQLite and isolated PostgreSQL migrations pass.
3. Bounded asynchronous crawl and deterministic SEO audits — unit-tested and controlled live worker verified with Celery solo pool.
4. Qdrant hybrid retrieval and grounded RAG — controlled service workflow verified; mock LLM only.
5. Connected Next.js dashboard — build- and browser-verified against live local APIs.
6. Production hardening — prefork runtime, authenticated tenant identity, durable automated E2E, retry/cancellation fault tests, and performance profiling remain pending.
7. Advanced product work — competitor gaps, recommendations, monitoring, graph/agent workflows, GEO, integrations, deployment, and reproducible research remain planned.

## Async Crawl and SEO Audit Worker

The API persists a crawl or audit run before dispatching the Celery task. The worker reconstructs the service container and writes progress to PostgreSQL. A partial unique index prevents multiple active crawl jobs for one tenant/project/website. Crawls persist individual pages and chunks through the existing indexing service, which skips vector/chunk replacement when the content hash is unchanged. A worker startup recovery task requeues pending and stale running jobs. Audit results are relational records with tenant scope and evidence; the deterministic audit engine labels indexability as unverified unless an external search provider is later integrated.

Run a worker locally from `backend/` with `uv run celery -A app.tasks.queue:celery_app worker --loglevel=INFO --queues=crawls,audits --pool=solo --concurrency=1`. This requires reachable Redis and PostgreSQL. Controlled integration passed with Celery's solo pool on the host. Celery prefork crashed inside its fast task tracer on the host's Python 3.14/macOS runtime and remains to be checked against the intended Linux production runtime. Recovery tasks are routed to the crawl queue consumed by the documented worker command.

## Key Tradeoffs

- Local deterministic providers first: this keeps development reproducible and testable without external credentials, but it is not the final retrieval quality target.
- Direct retrieval implementation: BM25, fusion, and provider contracts are implemented directly so the system is interview-defensible and not hidden behind a broad orchestration framework.
- LangGraph later: workflow orchestration is useful for the SEO Analyst agent, but premature until retrieval, evidence models, and citation validation are stable.
- Neo4j later: graph storage adds operational cost, so the MVP first proves content extraction, entity/topic generation, and link relationships.
