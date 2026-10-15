# ADR 005: Embedding Versioning, Reranking, and Grounded RAG

## Context

The platform needs real semantic embeddings, explicit search strategies, reranking, and citation-grounded RAG while keeping tests offline and deterministic. Embedding model changes can invalidate existing Qdrant vectors, so the system must avoid mixing incompatible vectors silently.

## Decision

Keep `DeterministicEmbeddingProvider` for tests and add `SentenceTransformerEmbeddingProvider` for local production use. The selected local model is `BAAI/bge-small-en-v1.5` because it is a practical BGE-family model for a MacBook-class development machine, uses 384-dimensional normalized vectors, and is much lighter than larger BGE variants.

Version Qdrant collections by embedding version and also store embedding provider, model, dimension, and version in each point payload. Add a CLI reindex command:

```bash
python -m app.cli reindex --tenant <tenant_id> --project <project_id>
```

Add a `Reranker` interface with `NoOpReranker` for tests/default local runs and `CrossEncoderReranker` for optional sentence-transformers use. Add grounded RAG behind an `LLMProvider` abstraction with a deterministic `MockLLMProvider` for offline tests.

## Alternatives

- Replace deterministic embeddings entirely with real models.
- Store all embedding versions in one Qdrant collection without payload filtering.
- Depend on a paid LLM for RAG tests.

## Tradeoffs

The default test path remains lightweight and reproducible, but real model smoke tests require installing optional model dependencies and downloading model weights. Versioned collections are operationally simple, though they require explicit reindexing after model changes.
