"""Consolidation ("sleep cycle", BUILD_PLAN.md §5.2 step 2): clusters a shopper's
recent episodes against their existing beliefs and asks qwen-max for belief
mutations — create / reinforce / revise / deprecate, each citing evidence.

Reads episodes/beliefs directly (a batch clustering read scoped to one shopper, not
a budget-capped `recall` for answering a live query) but every mutation is applied
through the MCP `revise_belief` / `forget` tools, so memory_audit stays the single,
audited record of what changed — see docs/DECISIONS.md.
"""

import json
import logging

from mcp_memory.consolidation_contract import (
    BeliefMutation,
    ConsolidationResponse,
    ValidationError,
    parse_consolidation_response,
)
from sqlalchemy import select

from app import db
from app.core.config import get_settings
from app.models import Belief, Episode
from app.models.belief import STATUS_DEPRECATED
from app.services import qwen
from app.services.memory_client import MemoryUnavailableError, memory_client

logger = logging.getLogger("memora.consolidation")
settings = get_settings()

_SYSTEM_PROMPT = (
    "You maintain long-term shopper preference beliefs for an e-commerce memory system. "
    "Given a shopper's existing beliefs and their recent behavioral episodes, decide what "
    "to create, reinforce, revise, or deprecate. Respond with strict JSON only, matching "
    'exactly this shape: {"mutations": [{"action": "create|reinforce|revise|deprecate", '
    '"belief_id": "<uuid, required unless action=create>", '
    '"statement": "<required for create/revise>", '
    '"category": "style|budget|size|brand|cadence|constraint (required for create)", '
    '"confidence": <0..1, required for create/reinforce/revise>, '
    '"evidence_episode_ids": ["<uuid>", ...], "reason": "<human-readable, cites evidence>"}]}. '
    "Only propose a mutation when the evidence genuinely supports it — an empty mutations "
    "list is a valid answer. Explicitly check new episodes against existing beliefs for "
    "contradictions (e.g. recent purchases exceeding a remembered budget) and propose a "
    "revise or deprecate that names the contradiction in its reason."
)


async def _load_context(store_id: str, shopper_id: str) -> tuple[list[dict], list[dict]]:
    async with db.async_session() as session:
        episodes = (
            await session.execute(
                select(Episode)
                .where(Episode.store_id == store_id, Episode.shopper_id == shopper_id)
                .order_by(Episode.created_at.desc())
                .limit(settings.consolidation_every_n_events)
            )
        ).scalars()
        beliefs = (
            await session.execute(
                select(Belief)
                .where(Belief.store_id == store_id, Belief.shopper_id == shopper_id)
                .where(Belief.status != STATUS_DEPRECATED)
            )
        ).scalars()

        episodes_out = [
            {"id": str(e.id), "kind": e.kind, "summary": e.summary, "intent": e.intent}
            for e in episodes
        ]
        beliefs_out = [
            {
                "id": str(b.id),
                "statement": b.statement,
                "category": b.category,
                "confidence": b.confidence,
            }
            for b in beliefs
        ]
    return episodes_out, beliefs_out


async def consolidate_shopper(store_id: str, shopper_id: str) -> ConsolidationResponse:
    episodes, beliefs = await _load_context(store_id, shopper_id)
    if not episodes:
        return ConsolidationResponse(mutations=[])

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"existing_beliefs": beliefs, "recent_episodes": episodes}),
        },
    ]

    response: ConsolidationResponse | None = None
    raw = ""
    for attempt in range(2):
        try:
            raw = await qwen.chat(messages, reasoning=True)
            response = parse_consolidation_response(raw)
            break
        except qwen.QwenUnavailableError as exc:
            logger.warning("qwen unavailable during consolidation, skipping: %s", exc)
            return ConsolidationResponse(mutations=[])
        except (ValidationError, ValueError) as exc:
            logger.warning(
                "consolidation contract validation failed (attempt %d): %s", attempt + 1, exc
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"That response was invalid: {exc}. Return corrected strict JSON only.",
                }
            )

    if response is None:
        logger.error("consolidation gave up after retry for shopper=%s", shopper_id)
        return ConsolidationResponse(mutations=[])

    for mutation in response.mutations:
        await _apply_mutation(store_id, shopper_id, mutation)

    return response


async def _apply_mutation(store_id: str, shopper_id: str, mutation: BeliefMutation) -> None:
    try:
        if mutation.action == "deprecate":
            await memory_client.forget(mutation.belief_id, reason=mutation.reason)
        elif mutation.action == "create":
            await memory_client.revise_belief(
                action="create",
                reason=mutation.reason,
                store_id=store_id,
                shopper_id=shopper_id,
                statement=mutation.statement,
                category=mutation.category,
                confidence=mutation.confidence,
                evidence_episode_ids=mutation.evidence_episode_ids,
            )
        else:  # reinforce | revise
            await memory_client.revise_belief(
                action=mutation.action,
                belief_id=mutation.belief_id,
                reason=mutation.reason,
                statement=mutation.statement,
                confidence=mutation.confidence,
                evidence_episode_ids=mutation.evidence_episode_ids,
            )
    except MemoryUnavailableError as exc:
        logger.error(
            "failed to apply consolidation mutation action=%s belief_id=%s: %s",
            mutation.action,
            mutation.belief_id,
            exc,
        )
