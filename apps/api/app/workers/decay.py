"""Hourly decay tick (BUILD_PLAN.md §5.2 step 3): ages every belief's confidence down
per its category half-life.

Reads the full belief table directly — a system-wide batch sweep, not a per-shopper
lookup, so it doesn't fit `recall`'s shopper-scoped, budget-capped shape. Every
confidence *mutation*, though, still goes through the MCP `revise_belief` tool
(action="decay") so memory_audit stays the single, complete record of what changed
and why, consistent with every other mutation path. See docs/DECISIONS.md.
"""

import logging
from datetime import datetime, timezone

from mcp_memory.ranking import decay_confidence, status_for_confidence
from sqlalchemy import select

from app import db
from app.models import Belief
from app.models.belief import STATUS_DEPRECATED
from app.services.memory_client import MemoryToolError, MemoryUnavailableError, memory_client

logger = logging.getLogger("memora.decay")


async def run_decay_tick() -> int:
    """Applies half-life decay to every active/decaying belief. Returns the count of
    beliefs whose confidence/status actually changed.
    """
    now = datetime.now(timezone.utc)

    async with db.async_session() as session:
        rows = (
            await session.execute(select(Belief).where(Belief.status != STATUS_DEPRECATED))
        ).scalars()
        # Snapshot to plain values while the session is open — the MCP calls below are
        # awaits against a different connection, so ORM objects shouldn't outlive this.
        candidates = [
            (b.id, b.confidence, b.decay_half_life_days, b.last_reinforced_at, b.status)
            for b in rows
        ]

    updated = 0
    for belief_id, confidence, half_life_days, last_reinforced_at, old_status in candidates:
        days_elapsed = (now - last_reinforced_at).total_seconds() / 86400
        if days_elapsed <= 0:
            continue

        new_confidence = decay_confidence(confidence, days_elapsed, half_life_days)
        new_status = status_for_confidence(new_confidence)

        if new_status == old_status and abs(new_confidence - confidence) < 1e-6:
            continue

        try:
            await memory_client.revise_belief(
                action="decay",
                belief_id=belief_id,
                confidence=new_confidence,
                reason=(
                    f"confidence decayed from {confidence:.2f} to {new_confidence:.2f} over "
                    f"{days_elapsed:.1f} days — status now {new_status}"
                ),
            )
            updated += 1
        except (MemoryUnavailableError, MemoryToolError) as exc:
            # MemoryToolError covers the belief having been deleted between this
            # tick's read snapshot and the write (e.g. a shopper deleted it via the
            # Inspector mid-tick) — log and move on rather than aborting the sweep.
            logger.error("decay tick: failed to update belief %s: %s", belief_id, exc)

    return updated
