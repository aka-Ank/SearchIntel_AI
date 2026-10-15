from app.embeddings.providers import DeterministicEmbeddingProvider


def test_deterministic_embedding_provider_is_stable_and_batched() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=16, version="test-v1")

    first = provider.embed_text("JavaScript SEO hydration")
    second = provider.embed_text("JavaScript SEO hydration")
    batch = provider.embed_batch(["JavaScript SEO hydration", "technical SEO"])

    assert first == second
    assert batch[0] == first
    assert len(first) == 16
    assert provider.metadata.provider == "deterministic"
    assert provider.metadata.version == "test-v1"
