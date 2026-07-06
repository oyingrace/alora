"""Hybrid recommendations (BUILD_PLAN.md §5.3): candidate products by embedding
similarity to (query ∪ active beliefs), filtered by hard constraints, reranked by
qwen-turbo. Falls back to similarity-only ordering if Qwen is unavailable —
CLAUDE.md architecture rule 4 names this exact endpoint as the graceful-degradation
example ("if Qwen API is down, /recs serves cached/similarity-only results").

Deleting a belief in the Inspector changes what `recall` returns, which changes the
search text here, which changes the ranking — that live feedback loop is the point
(BUILD_PLAN.md §5.3: "the money demo moment").
"""

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from app.services import qwen
from app.services.catalog import ProductResult, search_products
from app.services.embeddings import embed_cached
from app.services.memory_client import memory_client

logger = logging.getLogger("memora.recs")


class _RerankItem(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)


class _RerankResponse(BaseModel):
    rankings: list[_RerankItem] = Field(default_factory=list)


_RERANK_SYSTEM_PROMPT = (
    "Rerank these candidate products for this shopper by relevance, using their stated "
    "preferences and each product's similarity to their query. Respond with strict JSON "
    'only: {"rankings": [{"name": "<product name>", "score": <0..1>}, ...]}, most '
    "relevant first. Omit products that clearly don't fit."
)


async def get_recommendations(
    store_id: str,
    shopper_id: str,
    query: str = "",
    category: str | None = None,
    max_price: float | None = None,
    limit: int = 5,
) -> tuple[list[ProductResult], bool]:
    """Returns (recommendations, degraded)."""
    recall_result = await memory_client.recall(
        store_id=store_id, shopper_id=shopper_id, query=query
    )
    belief_statements = [b.statement for b in recall_result.beliefs]
    search_text = " ".join([query, *belief_statements]).strip()

    query_embedding = None
    if search_text:
        try:
            query_embedding = await embed_cached(search_text)
        except qwen.QwenUnavailableError:
            query_embedding = None

    candidates = await search_products(
        store_id,
        query_embedding=query_embedding,
        category=category,
        max_price=max_price,
        limit=max(limit * 2, limit),
    )
    if not candidates:
        return [], False

    try:
        raw = await qwen.chat(
            [
                {"role": "system", "content": _RERANK_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "shopper_beliefs": belief_statements,
                            "query": query,
                            "candidates": [
                                {
                                    "name": c.name,
                                    "category": c.category,
                                    "price": c.price,
                                    "similarity": round(c.similarity, 3),
                                }
                                for c in candidates
                            ],
                        }
                    ),
                },
            ],
            reasoning=False,
        )
        reranked = _RerankResponse.model_validate_json(raw)
    except (qwen.QwenUnavailableError, ValidationError, ValueError) as exc:
        logger.warning("recs rerank unavailable/invalid, serving similarity-only order: %s", exc)
        return candidates[:limit], True

    order = {item.name: i for i, item in enumerate(reranked.rankings)}
    ranked = sorted(candidates, key=lambda c: order.get(c.name, len(order) + 1))
    return ranked[:limit], False
