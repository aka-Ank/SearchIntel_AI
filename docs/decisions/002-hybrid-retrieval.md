# ADR 002: Direct Hybrid Retrieval with Reciprocal Rank Fusion

## Context

The platform must compare vector, BM25, hybrid, and hybrid plus reranker retrieval strategies. The retrieval flow should be transparent during interviews and evaluation.

## Decision

Implement dense retrieval, BM25 retrieval, and Reciprocal Rank Fusion directly. Expose strategy selection through the retrieval service and API.

## Alternatives

- Use a high-level RAG framework for retrieval.
- Use only vector retrieval in the MVP.

## Tradeoffs

Direct implementation takes more code, but it makes scoring, filtering, evaluation, and debugging explicit. It also supports exact-match SEO terms where BM25 can outperform embeddings.
