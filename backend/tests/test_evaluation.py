from app.evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


def test_retrieval_metric_calculations() -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"b", "d"}

    assert precision_at_k(retrieved, relevant, 2) == 0.5
    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert round(ndcg_at_k(retrieved, relevant, 3), 4) == 0.3869
