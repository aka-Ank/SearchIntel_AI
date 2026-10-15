# ADR 001: Local Deterministic Providers for the First Slice

## Context

The platform needs embeddings, vector search, and retrieval behavior before external model keys, Qdrant, and production infrastructure are guaranteed to be available.

## Decision

Implement deterministic local embedding and in-memory retrieval providers for the first vertical slice. Keep them behind provider interfaces so production providers can replace them without changing API or service contracts.

## Alternatives

- Start directly with Qdrant and BGE embeddings.
- Mock all retrieval behavior without real indexing.

## Tradeoffs

Local deterministic providers are lower quality than production embeddings, but they make tests reproducible and keep the first slice functional. They are real enough to validate tenant filtering, ranking flow, and API response shape.
