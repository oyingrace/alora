"""MCP server exposing Memora's memory layer.

Four tools only: recall, write_episode, revise_belief, forget. This is the sole path
the agent runtime uses to touch memory (CLAUDE.md architecture rule 1) — nothing here
should ever be bypassed by a direct DB query from apps/api.

Phase 0 scaffold: DB wiring, contracts, and hard budget enforcement in `recall` are
real; the semantic ranker (cosine similarity x confidence x recency) is a naive
recency+confidence sort for now and gets replaced with embeddings in Phase 1.
"""

import uuid
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from mcp_memory.config import get_settings
from mcp_memory.db import async_session
from mcp_memory.models import ACTION_DEPRECATE, ACTION_REVISE, Belief, Episode, MemoryAudit
from mcp_memory.models import STATUS_DEPRECATED
from mcp_memory.schemas import (
    BeliefOut,
    EpisodeSummaryOut,
    ForgetResult,
    RecallResult,
    ReviseBeliefResult,
    WriteEpisodeResult,
)

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
) -> RecallResult:
    """Return active beliefs + recent episode summaries greedy-packed into budget_tokens.

    `query` is accepted now for API stability; semantic reranking against it lands in
    Phase 1 once embeddings are wired up. Today's ranking is confidence desc, then
    recency desc.
    """
    budget = budget_tokens or settings.default_recall_budget_tokens
    used = 0
    beliefs_out: list[BeliefOut] = []
    episodes_out: list[EpisodeSummaryOut] = []

    async with async_session() as session:
        belief_rows = (
            await session.execute(
                select(Belief)
                .where(Belief.store_id == store_id, Belief.shopper_id == shopper_id)
                .where(Belief.status != STATUS_DEPRECATED)
                .order_by(Belief.confidence.desc(), Belief.last_reinforced_at.desc())
            )
        ).scalars()

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


@mcp.tool()
async def write_episode(
    store_id: str,
    shopper_id: str,
    session_id: str,
    kind: str,
    payload: dict,
    summary: str | None = None,
    intent: str = "unknown",
) -> WriteEpisodeResult:
    """Record a raw behavioral event. Summarization/intent classification (qwen-turbo)
    happens upstream in apps/api before this is called; this tool only persists.
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
        )
        session.add(episode)
        await session.commit()
        return WriteEpisodeResult(episode_id=episode.id)


@mcp.tool()
async def revise_belief(
    belief_id: uuid.UUID,
    evidence_episode_ids: list[uuid.UUID],
    reason: str,
    new_statement: str | None = None,
    new_confidence: float | None = None,
) -> ReviseBeliefResult:
    """Mutate a belief and write a human-readable memory_audit row (rule 2)."""
    async with async_session() as session:
        belief = await session.get(Belief, belief_id)
        if belief is None:
            raise ValueError(f"belief {belief_id} not found")

        if new_statement is not None:
            belief.statement = new_statement
        if new_confidence is not None:
            belief.confidence = new_confidence
        belief.evidence = list({*belief.evidence, *evidence_episode_ids})
        belief.last_reinforced_at = datetime.now(timezone.utc)

        session.add(
            MemoryAudit(
                belief_id=belief.id,
                store_id=belief.store_id,
                shopper_id=belief.shopper_id,
                action=ACTION_REVISE,
                reason=reason,
            )
        )
        await session.commit()
        return ReviseBeliefResult(
            belief_id=belief.id, status=belief.status, confidence=belief.confidence
        )


@mcp.tool()
async def forget(belief_id: uuid.UUID, reason: str) -> ForgetResult:
    """Mark a belief deprecated (soft delete) and audit the deletion, verbatim reason
    shown in the Memory Inspector.
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
                action=ACTION_DEPRECATE,
                reason=reason,
            )
        )
        await session.commit()
        return ForgetResult(belief_id=belief.id, status=belief.status)


if __name__ == "__main__":
    mcp.run()
