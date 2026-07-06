"""Runs one persona's scripted sessions twice — once per "arm" — and records the
three BUILD_PLAN.md §7 metrics per session: rec relevance (LLM-judged), tokens
spent, and (for personas with a scripted preference shift) how many sessions after
the shift it took recs to become relevant again.

Baseline arm skips writing any episodes at all and calls /recs cold every session —
"similarity-only recs, no memory" (BUILD_PLAN.md §7) means there's no belief/episode
history behind the query, not just a fresh shopper_id. Memora arm uses one persistent
shopper_id for the whole persona: events accumulate and consolidation runs at the end
of every session ("sleep cycle" at session end, rather than the event-count cadence
/events normally uses — deterministic and easier to reason about for a benchmark).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.services import qwen
from app.services.embeddings import embed_cached
from app.services.intent import annotate_episode
from app.services.memory_client import memory_client
from app.services.recs import get_recommendations
from app.workers.consolidation import consolidate_shopper
from bench.llm_judge import judge_relevance
from bench.personas import Persona, SessionScript

RELEVANCE_RECOVERY_THRESHOLD = 0.5


@dataclass
class SessionResult:
    relevance: float
    tokens: int
    degraded: bool


@dataclass
class ArmResult:
    arm: str
    sessions: list[SessionResult] = field(default_factory=list)

    @property
    def avg_relevance(self) -> float:
        if not self.sessions:
            return 0.0
        return sum(s.relevance for s in self.sessions) / len(self.sessions)

    @property
    def avg_tokens(self) -> float:
        if not self.sessions:
            return 0.0
        return sum(s.tokens for s in self.sessions) / len(self.sessions)


async def _write_event(
    store_id: str, shopper_id: str, session_id: str, kind: str, payload: dict
) -> None:
    annotation = await annotate_episode(kind, payload)
    embedding = None
    try:
        embedding = await embed_cached(annotation.summary)
    except qwen.QwenUnavailableError:
        embedding = None
    await memory_client.write_episode(
        store_id=store_id,
        shopper_id=shopper_id,
        session_id=session_id,
        kind=kind,
        payload=payload,
        summary=annotation.summary,
        intent=annotation.intent,
        embedding=embedding,
    )


async def _run_session(
    store_id: str, shopper_id: str, script: SessionScript, *, persistent: bool
) -> SessionResult:
    session_id = f"session-{uuid.uuid4().hex}"
    qwen.reset_token_usage()

    if persistent:
        for kind, payload in script.events:
            await _write_event(store_id, shopper_id, session_id, kind, payload)
        await consolidate_shopper(store_id, shopper_id)

    # limit=1: with only two products per demo category, a larger limit would return
    # both regardless of ranking quality and mask any baseline-vs-memora difference —
    # the interesting question is whether reranking puts the *right one* first.
    recs, degraded = await get_recommendations(
        store_id, shopper_id, query=script.recs_query, category=script.category, limit=1
    )
    tokens = sum(u["total_tokens"] or 0 for u in qwen.get_token_usage())

    relevance = await judge_relevance(
        script.ideal_description,
        [
            {"name": r.name, "category": r.category, "price": r.price, "description": r.description}
            for r in recs
        ],
    )
    return SessionResult(relevance=relevance, tokens=tokens, degraded=degraded)


async def run_persona_arm(store_id: str, persona: Persona, *, persistent: bool) -> ArmResult:
    arm = "memora" if persistent else "baseline"
    result = ArmResult(arm=arm)
    shopper_id = f"bench-{persona.name.lower().replace(' ', '-')}-{arm}-{uuid.uuid4().hex[:8]}"

    for script in persona.sessions:
        session_shopper_id = shopper_id if persistent else f"{shopper_id}-{uuid.uuid4().hex[:8]}"
        result.sessions.append(
            await _run_session(store_id, session_shopper_id, script, persistent=persistent)
        )

    return result


def sessions_to_recover(sessions: list[SessionResult], shift_index: int) -> int | None:
    """How many sessions after `shift_index` (inclusive) it took relevance to cross
    RELEVANCE_RECOVERY_THRESHOLD. None if it never did.
    """
    for i, s in enumerate(sessions[shift_index:]):
        if s.relevance >= RELEVANCE_RECOVERY_THRESHOLD:
            return i
    return None
