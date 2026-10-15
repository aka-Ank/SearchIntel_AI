# ADR 004: Persistent Crawl Storage with Qdrant Vector Retrieval

## Context

The first slice used process-local project state, BM25 state, and vector storage. The next milestone requires crawled pages and chunks to persist in PostgreSQL and dense retrieval to use Qdrant by default when configured.

## Decision

Use SQLAlchemy repositories for tenant, project, website, page, content chunk, and crawl job persistence. Use Alembic for schema migrations. Keep vector storage behind the existing `VectorStore` protocol and add a `QdrantVectorStore` implementation with tenant, project, website, page, chunk, URL, title, and heading metadata in each point payload.

BM25 remains a lightweight local index, but it is rebuilt from persisted chunks at query time when a persisted chunk loader is configured. This keeps PostgreSQL as the authoritative corpus while avoiding premature search-service infrastructure.

## Alternatives

- Store all search state in memory and defer persistence.
- Move BM25 to a dedicated external search engine immediately.
- Replace the local crawler with a distributed worker system immediately.

## Tradeoffs

The current BM25 rebuild approach is simple and deterministic for the MVP, but it will need caching or a durable lexical index as the corpus grows. The crawler still runs in-process for local development, but service boundaries now allow moving crawl execution to Redis-backed workers later.
