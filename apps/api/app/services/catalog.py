"""Product catalog: embedding + similarity search. Products aren't governed by
architecture rule 1 (that rule is about the episodes/beliefs memory tables) — direct
DB access here is fine.
"""

import hashlib
import logging

import redis.asyncio as redis
from sqlalchemy import select

from app import db
from app.core.config import get_settings
from app.models import Product
from app.services import qwen
from app.services.embeddings import embed_cached

logger = logging.getLogger("memora.catalog")
settings = get_settings()

_VISION_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30
_VISION_PROMPT = (
    "Describe this product's visual style in 3-6 short tags (e.g. minimalist, leather, "
    "warm-tones, ornate). Respond with a comma-separated list only."
)


async def embed_product_text(name: str, description: str, category: str) -> list[float] | None:
    text = f"{name}. {category}. {description}".strip()
    try:
        return await embed_cached(text)
    except qwen.QwenUnavailableError as exc:
        logger.warning("qwen unavailable while embedding product %r: %s", name, exc)
        return None


async def tag_product_image(image_url: str) -> str | None:
    """qwen-vl-max visual tagging, cached by image URL content hash (CLAUDE.md: cache
    VL tags). Best-effort — a tagging failure must never block a catalog sync.
    """
    key = f"memora:vision:{hashlib.sha256(image_url.encode()).hexdigest()}"
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    cached = await redis_client.get(key)
    if cached is not None:
        return cached

    try:
        tags = await qwen.vision_tag(image_url, _VISION_PROMPT)
    except qwen.QwenUnavailableError as exc:
        logger.warning("qwen unavailable while tagging image %s: %s", image_url, exc)
        return None

    await redis_client.set(key, tags, ex=_VISION_CACHE_TTL_SECONDS)
    return tags


class ProductResult:
    def __init__(self, product: Product, similarity: float) -> None:
        self.id = product.id
        self.name = product.name
        self.description = product.description
        self.category = product.category
        self.price = product.price
        self.currency = product.currency
        self.image_url = product.image_url
        self.similarity = similarity


async def search_products(
    store_id: str,
    query_embedding: list[float] | None,
    category: str | None = None,
    max_price: float | None = None,
    limit: int = 5,
) -> list[ProductResult]:
    """Candidate products by embedding similarity to the query, filtered by hard
    constraints (category, max_price) — BUILD_PLAN.md §5.3.
    """
    async with db.async_session() as session:
        stmt = select(Product).where(Product.store_id == store_id)
        if category:
            stmt = stmt.where(Product.category == category)
        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)

        if query_embedding is not None:
            distance = Product.embedding.cosine_distance(query_embedding)
            stmt = stmt.where(Product.embedding.is_not(None)).order_by(distance).limit(limit)
        else:
            stmt = stmt.order_by(Product.created_at.desc()).limit(limit)

        rows = (await session.execute(stmt)).scalars().all()

    results = []
    for product in rows:
        similarity = 0.0
        if query_embedding is not None and product.embedding is not None:
            from mcp_memory.ranking import cosine_similarity

            similarity = cosine_similarity(query_embedding, product.embedding)
        results.append(ProductResult(product, similarity))
    return results
