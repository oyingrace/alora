"""MCP server exposing Memora's memory layer.

Four tools only: recall, write_episode, revise_belief, forget. This is the sole path
the agent runtime uses to touch memory (CLAUDE.md architecture rule 1) — nothing here
should ever be bypassed by a direct DB query from apps/api.

`revise_belief` doubles as the create path (belief_id=None) so "create / reinforce /
revise / decay" from the consolidation and decay workers all funnel through one
audited mutation tool, matching the four-tools boundary in BUILD_PLAN.md §4 without
adding a fifth tool. Callers pass an explicit `action` rather than having it inferred,
since a decay-driven confidence *decrease* would otherwise be misread as "reinforce".
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from mcp_memory.config import get_settings
from mcp_memory.models import (
    DECAY_HALF_LIFE_DAYS,
    DEFAULT_HALF_LIFE_DAYS,
    STATUS_DEPRECATED,
    Belief,
    Episode,
    MemoryAudit,
)
from mcp_memory.db import async_session
from mcp_memory.ranking import cosine_similarity, recall_rank_score, status_for_confidence
from mcp_memory.schemas import (
    BeliefOut,
    EpisodeSummaryOut,
    ForgetResult,
    RecallResult,
    ReviseBeliefResult,
    WriteEpisodeResult,
)

ReviseAction = Literal["create", "reinforce", "revise", "decay"]
ForgetAction = Literal["deprecate", "user_delete"]

settings = get_settings()
mcp = FastMCP("memora-memory")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (chars/4) used only to enforce the budget cheaply."""
    return max(1, len(text) // 4)


@mcp.tool()
async def recall(
    store_id: str,
    shopper_id: str,
    query: str,
    budget_tokens: int | None = None,
    query_embedding: list[float] | None = None,
) -> RecallResult:
    """Return active beliefs + recent episode summaries greedy-packed into budget_tokens.

    Ranks by cosine similarity x confidence x recency (BUILD_PLAN.md §5.3) when
    `query_embedding` is supplied by the caller (apps/api embeds `query` before
    calling this tool); falls back to a neutral-similarity confidence/recency sort
    when it isn't, so recall degrades gracefully rather than failing.
    """
    budget = budget_tokens or settings.default_recall_budget_tokens
    used = 0
    beliefs_out: list[BeliefOut] = []
    episodes_out: list[EpisodeSummaryOut] = []
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        belief_rows = list(
            (
                await session.execute(
                    select(Belief)
                    .where(Belief.store_id == store_id, Belief.shopper_id == shopper_id)
                    .where(Belief.status != STATUS_DEPRECATED)
                )
            ).scalars()
        )

        def _score(belief: Belief) -> float:
            similarity = (
                cosine_similarity(query_embedding, belief.embedding)
                if query_embedding is not None and belief.embedding is not None
                else 1.0
            )
            days_since = (now - belief.last_reinforced_at).total_seconds() / 86400
            return recall_rank_score(
                confidence=belief.confidence,
                similarity=similarity,
                days_since_reinforced=days_since,
                half_life_days=belief.decay_half_life_days,
            )

        belief_rows.sort(key=_score, reverse=True)

        for belief in belief_rows:
            cost = _estimate_tokens(belief.statement)
            if used + cost > budget:
                break
            used += cost
            beliefs_out.append(
                BeliefOut(
                    id=belief.id,
                    statement=belief.statement,
                    category=belief.category,
                    confidence=belief.confidence,
                    status=belief.status,
                )
            )

        episode_rows = (
            await session.execute(
                select(Episode)
                .where(Episode.store_id == store_id, Episode.shopper_id == shopper_id)
                .order_by(Episode.created_at.desc())
                .limit(3)
            )
        ).scalars()

        for episode in episode_rows:
            cost = _estimate_tokens(episode.summary or "")
            if used + cost > budget:
                break
            used += cost
            episodes_out.append(
                EpisodeSummaryOut(id=episode.id, kind=episode.kind, summary=episode.summary)
            )

    return RecallResult(
        beliefs=beliefs_out,
        episodes=episodes_out,
        budget_tokens=budget,
        budget_used_tokens=used,
    )


async def _detect_anomalous_purchase(
    session, store_id: str, shopper_id: str, embedding: list[float] | None, exclude_id: uuid.UUID
) -> bool:
    """Cheap gift-detection heuristic (BUILD_PLAN.md §5.2 step 1): compare this
    purchase's embedding against the centroid of the shopper's prior purchases.
    """
    if embedding is None:
        return False

    rows = (
        await session.execute(
            select(Episode.embedding)
            .where(
                Episode.store_id == store_id,
                Episode.shopper_id == shopper_id,
                Episode.kind == "purchase",
                Episode.id != exclude_id,
                Episode.embedding.is_not(None),
            )
            .order_by(Episode.created_at.desc())
            .limit(20)
        )
    ).scalars()
    history = [e for e in rows if e is not None]

    if len(history) < settings.anomaly_min_purchase_history:
        return False

    centroid = [sum(dim) / len(history) for dim in zip(*history)]
    similarity = cosine_similarity(embedding, centroid)
    return similarity < settings.anomaly_similarity_threshold


@mcp.tool()
async def write_episode(
    store_id: str,
    shopper_id: str,
    session_id: str,
    kind: str,
    payload: dict,
    summary: str | None = None,
    intent: str = "unknown",
    embedding: list[float] | None = None,
) -> WriteEpisodeResult:
    """Record a raw behavioral event. Summarization/intent classification (qwen-turbo)
    and embedding computation happen upstream in apps/api before this is called; this
    tool persists and, for purchases, flags whether it looks anomalous relative to the
    shopper's history so the caller can queue a "was that a gift?" clarification.
    """
    async with async_session() as session:
        episode = Episode(
            store_id=store_id,
            shopper_id=shopper_id,
            session_id=session_id,
            kind=kind,
            payload=payload,
            summary=summary,
            intent=intent,
            embedding=embedding,
        )
        session.add(episode)
        await session.flush()

        anomalous = False
        if kind == "purchase":
            anomalous = await _detect_anomalous_purchase(
                session, store_id, shopper_id, embedding, episode.id
            )

        await session.commit()
        return WriteEpisodeResult(episode_id=episode.id, anomalous=anomalous)


@mcp.tool()
async def revise_belief(
    action: ReviseAction,
    reason: str,
    belief_id: uuid.UUID | None = None,
    store_id: str | None = None,
    shopper_id: str | None = None,
    statement: str | None = None,
    category: str | None = None,
    confidence: float | None = None,
    evidence_episode_ids: list[uuid.UUID] | None = None,
) -> ReviseBeliefResult:
    """Create (action="create") or mutate (action="reinforce"/"revise"/"decay", with
    belief_id set) a belief, always writing a human-readable memory_audit row (rule 2).
    `action` is caller-supplied rather than inferred, since a decay-driven confidence
    drop must never be logged as "reinforce".
    """
    evidence_episode_ids = evidence_episode_ids or []

    async with async_session() as session:
        if action == "create":
            if belief_id is not None:
                raise ValueError('action="create" must not include belief_id')
            if not (store_id and shopper_id and statement and category and confidence is not None):
                raise ValueError(
                    'action="create" requires store_id, shopper_id, statement, category, '
                    "and confidence"
                )
            belief = Belief(
                store_id=store_id,
                shopper_id=shopper_id,
                statement=statement,
                category=category,
                confidence=confidence,
                status=status_for_confidence(confidence),
                evidence=evidence_episode_ids,
                decay_half_life_days=DECAY_HALF_LIFE_DAYS.get(category, DEFAULT_HALF_LIFE_DAYS),
            )
            session.add(belief)
        else:
            if belief_id is None:
                raise ValueError(f"action={action!r} requires belief_id")
            belief = await session.get(Belief, belief_id)
            if belief is None:
                raise ValueError(f"belief {belief_id} not found")

            if statement is not None:
                belief.statement = statement
            if confidence is not None:
                belief.confidence = confidence
                belief.status = status_for_confidence(confidence)
            if evidence_episode_ids:
                belief.evidence = list({*belief.evidence, *evidence_episode_ids})
            belief.last_reinforced_at = datetime.now(timezone.utc)

        await session.flush()

        session.add(
            MemoryAudit(
                belief_id=belief.id,
                store_id=belief.store_id,
                shopper_id=belief.shopper_id,
                action=action,
                reason=reason,
            )
        )
        await session.commit()
        return ReviseBeliefResult(
            belief_id=belief.id, status=belief.status, confidence=belief.confidence
        )


@mcp.tool()
async def forget(
    belief_id: uuid.UUID, reason: str, action: ForgetAction = "deprecate"
) -> ForgetResult:
    """Mark a belief deprecated (soft delete) and audit the deletion, verbatim reason
    shown in the Memory Inspector. `action="user_delete"` when the shopper deletes it
    themselves in the Inspector; `action="deprecate"` (default) for system-driven
    single-shot deprecation, e.g. a contradiction detected during consolidation.
    """
    async with async_session() as session:
        belief = await session.get(Belief, belief_id)
        if belief is None:
            raise ValueError(f"belief {belief_id} not found")

        belief.status = STATUS_DEPRECATED
        session.add(
            MemoryAudit(
                belief_id=belief.id,
                store_id=belief.store_id,
                shopper_id=belief.shopper_id,
                action=action,
                reason=reason,
            )
        )
        await session.commit()
        return ForgetResult(belief_id=belief.id, status=belief.status)


if __name__ == "__main__":
    mcp.run()
