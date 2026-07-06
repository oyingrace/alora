import asyncio
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app import db
from app.core.config import get_settings
from app.models import Episode
from app.schemas.events import EventIn, EventOut
from app.services import qwen
from app.services.embeddings import embed_cached
from app.services.intent import annotate_episode
from app.services.memory_client import MemoryUnavailableError, memory_client
from app.workers.consolidation import consolidate_shopper

logger = logging.getLogger("memora.events")
router = APIRouter(tags=["events"])
settings = get_settings()


async def _episode_count(store_id: str, shopper_id: str) -> int:
    async with db.async_session() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(Episode)
                .where(Episode.store_id == store_id, Episode.shopper_id == shopper_id)
            )
        ).scalar_one()


@router.post("/events", response_model=EventOut)
async def ingest_event(event: EventIn) -> EventOut:
    """Ingest one behavioral event: summarize + classify intent (qwen-turbo), embed
    the summary, and persist through the MCP `write_episode` tool — the only path to
    the episodes table (CLAUDE.md architecture rule 1).
    """
    annotation = await annotate_episode(event.kind, event.payload)

    embedding: list[float] | None = None
    try:
        embedding = await embed_cached(annotation.summary)
    except qwen.QwenUnavailableError as exc:
        logger.warning("embedding unavailable during event ingest, storing without one: %s", exc)

    try:
        result = await memory_client.write_episode(
            store_id=event.store_id,
            shopper_id=event.shopper_id,
            session_id=event.session_id,
            kind=event.kind,
            payload=event.payload,
            summary=annotation.summary,
            intent=annotation.intent,
            embedding=embedding,
        )
    except MemoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail="memory layer unavailable") from exc

    count = await _episode_count(event.store_id, event.shopper_id)
    if count % settings.consolidation_every_n_events == 0:
        # Fire-and-forget: the qwen-max consolidation call shouldn't block this response.
        asyncio.create_task(consolidate_shopper(event.store_id, event.shopper_id))

    needs_clarification = (
        event.kind == "purchase" and result.anomalous and annotation.intent == "unknown"
    )
    return EventOut(episode_id=str(result.episode_id), needs_clarification=needs_clarification)
