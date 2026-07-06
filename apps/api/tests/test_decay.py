import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import db
from app.models import Belief, MemoryAudit
from app.services.memory_client import memory_client
from app.workers.decay import run_decay_tick


async def _backdate(belief_id: uuid.UUID, days_ago: float) -> None:
    async with db.async_session() as session:
        belief = await session.get(Belief, belief_id)
        belief.last_reinforced_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        await session.commit()


@pytest.mark.asyncio
async def test_decay_tick_lowers_confidence_and_audits_as_decay(connected_memory_client) -> None:
    created = await memory_client.revise_belief(
        action="create",
        reason="test setup",
        store_id="demo",
        shopper_id=f"shopper-{uuid.uuid4().hex}",
        statement="Budget conscious",
        category="budget",  # 30-day half-life
        confidence=1.0,
    )
    await _backdate(created.belief_id, days_ago=30)

    updated_count = await run_decay_tick()
    assert updated_count >= 1

    async with db.async_session() as session:
        belief = await session.get(Belief, created.belief_id)
        audit_rows = (
            await session.execute(
                select(MemoryAudit)
                .where(MemoryAudit.belief_id == created.belief_id)
                .order_by(MemoryAudit.created_at)
            )
        ).scalars().all()

    assert math.isclose(belief.confidence, 0.5, rel_tol=0.05)
    assert audit_rows[-1].action == "decay"


@pytest.mark.asyncio
async def test_decay_tick_is_noop_for_freshly_reinforced_beliefs(connected_memory_client) -> None:
    created = await memory_client.revise_belief(
        action="create",
        reason="test setup",
        store_id="demo",
        shopper_id=f"shopper-{uuid.uuid4().hex}",
        statement="Recently confirmed preference",
        category="style",
        confidence=0.8,
    )

    await run_decay_tick()

    async with db.async_session() as session:
        belief = await session.get(Belief, created.belief_id)
    assert belief.confidence == 0.8
    assert belief.status == "active"
