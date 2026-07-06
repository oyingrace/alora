import math

from mcp_memory.ranking import (
    cosine_similarity,
    decay_confidence,
    recall_rank_score,
    recency_weight,
    status_for_confidence,
)


def test_decay_confidence_at_one_half_life() -> None:
    assert math.isclose(decay_confidence(1.0, 30, 30), 0.5, rel_tol=1e-9)


def test_decay_confidence_at_two_half_lives() -> None:
    assert math.isclose(decay_confidence(1.0, 60, 30), 0.25, rel_tol=1e-9)


def test_decay_confidence_no_elapsed_time_is_noop() -> None:
    assert decay_confidence(0.8, 0, 30) == 0.8


def test_decay_confidence_zero_half_life_is_noop_guard() -> None:
    assert decay_confidence(0.8, 10, 0) == 0.8


def test_status_thresholds() -> None:
    assert status_for_confidence(0.9) == "active"
    assert status_for_confidence(0.3) == "active"  # boundary: < 0.3 is decaying
    assert status_for_confidence(0.29) == "decaying"
    assert status_for_confidence(0.15) == "decaying"  # boundary: < 0.15 is deprecated
    assert status_for_confidence(0.14) == "deprecated"
    assert status_for_confidence(0.0) == "deprecated"


def test_budget_belief_decays_faster_than_size_belief() -> None:
    # budget half-life 30d vs size half-life 365d — same elapsed time, budget decays more
    elapsed = 60
    budget_confidence = decay_confidence(1.0, elapsed, half_life_days=30)
    size_confidence = decay_confidence(1.0, elapsed, half_life_days=365)
    assert budget_confidence < size_confidence


def test_cosine_similarity_identical_vectors() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0, rel_tol=1e-9)


def test_cosine_similarity_orthogonal_vectors() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_cosine_similarity_mismatched_lengths_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0]) == 0.0


def test_cosine_similarity_zero_vector_is_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_returns_plain_float_for_numpy_inputs() -> None:
    # pgvector returns embeddings as numpy arrays; a numpy scalar result (e.g.
    # float32) isn't JSON-serializable, which broke /recs's qwen rerank payload.
    import numpy as np

    result = cosine_similarity(np.array([1.0, 0.0], dtype=np.float32), np.array([1.0, 0.0], dtype=np.float32))
    assert type(result) is float


def test_recency_weight_decreases_over_time() -> None:
    assert recency_weight(0) == 1.0
    assert recency_weight(30, half_life_days=30) < recency_weight(1, half_life_days=30)


def test_recall_rank_score_prefers_similar_confident_recent_beliefs() -> None:
    high = recall_rank_score(confidence=0.9, similarity=0.9, days_since_reinforced=1)
    low = recall_rank_score(confidence=0.3, similarity=0.2, days_since_reinforced=200)
    assert high > low


def test_recall_rank_score_neutral_similarity_falls_back_to_confidence_recency() -> None:
    score = recall_rank_score(confidence=0.8, similarity=1.0, days_since_reinforced=0)
    assert math.isclose(score, 0.8, rel_tol=1e-9)
