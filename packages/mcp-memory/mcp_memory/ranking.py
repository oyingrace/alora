"""Pure math for belief decay and recall ranking. No DB/IO — kept separate so the
consolidation/decay contracts are directly unit-testable (BUILD_PLAN.md §7 Phase 1).
"""

import math

from mcp_memory.models import DECAYING_THRESHOLD, DEPRECATED_THRESHOLD, STATUS_ACTIVE
from mcp_memory.models import STATUS_DECAYING, STATUS_DEPRECATED


def decay_confidence(confidence: float, days_elapsed: float, half_life_days: int) -> float:
    """Exponential half-life decay: confidence halves every `half_life_days`."""
    if days_elapsed <= 0 or half_life_days <= 0:
        return confidence
    return confidence * (0.5 ** (days_elapsed / half_life_days))


def status_for_confidence(confidence: float) -> str:
    """Maps a (possibly decayed) confidence value to a belief status."""
    if confidence < DEPRECATED_THRESHOLD:
        return STATUS_DEPRECATED
    if confidence < DECAYING_THRESHOLD:
        return STATUS_DECAYING
    return STATUS_ACTIVE


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # `a`/`b` may be numpy arrays (pgvector returns them from the DB), so truthiness
    # checks like `not a` are ambiguous for multi-element arrays — use len()/None checks.
    if a is None or b is None or len(a) == 0 or len(b) == 0 or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def recency_weight(days_since_reinforced: float, half_life_days: int = 30) -> float:
    """Recency alone, decoupled from confidence — used as a ranking factor."""
    if days_since_reinforced <= 0:
        return 1.0
    return 0.5 ** (days_since_reinforced / max(half_life_days, 1))


def recall_rank_score(
    confidence: float,
    similarity: float,
    days_since_reinforced: float,
    half_life_days: int = 30,
) -> float:
    """cosine similarity x confidence x recency (BUILD_PLAN.md §5.3 ranking algorithm).

    `similarity` should be 1.0 (neutral) when no query embedding is available, so
    recall degrades to a confidence x recency sort rather than zeroing everything out.
    """
    return confidence * similarity * recency_weight(days_since_reinforced, half_life_days)
