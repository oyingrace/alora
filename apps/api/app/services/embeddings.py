"""Content-hash keyed embedding cache (CLAUDE.md: "Cache embeddings... content-hash
keyed") — wraps app.services.qwen.embed so repeated text never re-pays the API call.
"""

import hashlib
import json
import logging

import redis.asyncio as redis

from app.core.config import get_settings
from app.services import qwen

logger = logging.getLogger("memora.embeddings")

CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
_CACHE_KEY_PREFIX = "memora:embed"

settings = get_settings()
_redis: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}:{model}:{digest}"


async def embed_cached(text: str, *, model: str | None = None) -> list[float]:
    """Embed `text`, serving from the Redis cache when the content hash matches."""
    resolved_model = model or settings.model_embed
    key = _cache_key(text, resolved_model)

    cached = await _redis.get(key)
    if cached is not None:
        return json.loads(cached)

    vectors = await qwen.embed([text], model=resolved_model)
    vector = vectors[0]
    await _redis.set(key, json.dumps(vector), ex=CACHE_TTL_SECONDS)
    return vector
