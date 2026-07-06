"""Ephemeral session memory for anonymous shoppers — CLAUDE.md architecture rule 5:
"Anonymous shoppers: session memory in Redis with TTL only. Persistence requires the
explicit opt-in flag from the consent banner." This store never touches Postgres;
it's what /events and /chat fall back to when the shopper hasn't opted in.
"""

import json
import time

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
_redis: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)

SESSION_TTL_SECONDS = 60 * 60  # 1 hour — gone with the browsing session
_MAX_EVENTS = 50


def _key(session_id: str) -> str:
    return f"memora:session:{session_id}:events"


async def append_event(session_id: str, kind: str, payload: dict) -> None:
    key = _key(session_id)
    entry = json.dumps({"kind": kind, "payload": payload, "ts": time.time()})
    await _redis.rpush(key, entry)
    await _redis.ltrim(key, -_MAX_EVENTS, -1)
    await _redis.expire(key, SESSION_TTL_SECONDS)


async def get_events(session_id: str) -> list[dict]:
    raw = await _redis.lrange(_key(session_id), 0, -1)
    return [json.loads(r) for r in raw]
