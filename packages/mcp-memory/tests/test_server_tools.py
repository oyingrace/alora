import uuid

import pytest
from sqlalchemy import select

from mcp_memory.db import async_session
from mcp_memory.models import ACTION_CREATE, ACTION_DECAY, ACTION_REINFORCE, MemoryAudit
from mcp_memory.server import forget, recall, revise_belief, write_episode

STORE = "demo"
SHOPPER = "shopper-1"


def _unit_vector(hot_index: int, dim: int = 1024) -> list[float]:
    vec = [0.0] * dim
    vec[hot_index] = 1.0
    return vec


@pytest.mark.asyncio
async def test_write_episode_persists() -> None:
    result = await write_episode(
        store_id=STORE,
        shopper_id=SHOPPER,
        session_id="s1",
        kind="view",
        payload={"product_id": "p1"},
        summary="Viewed a leather bag",
        intent="self",
    )
    assert result.episode_id is not None
    assert result.anomalous is False


@pytest.mark.asyncio
async def test_write_episode_not_anomalous_with_insufficient_history() -> None:
    normal = _unit_vector(0)
    weird = _unit_vector(7)

    for _ in range(2):
        await write_episode(
            store_id=STORE,
            shopper_id=SHOPPER,
            session_id="s1",
            kind="purchase",
            payload={},
            embedding=normal,
        )

    result = await write_episode(
        store_id=STORE,
        shopper_id=SHOPPER,
        session_id="s1",
        kind="purchase",
        payload={},
        embedding=weird,
    )
    # only 2 prior purchases — below anomaly_min_purchase_history (3), so no flag yet
    assert result.anomalous is False


@pytest.mark.asyncio
async def test_write_episode_flags_anomalous_purchase() -> None:
    normal = _unit_vector(0)
    weird = _unit_vector(7)

    for _ in range(4):
        await write_episode(
            store_id=STORE,
            shopper_id=SHOPPER,
            session_id="s1",
            kind="purchase",
            payload={},
            embedding=normal,
        )

    result = await write_episode(
        store_id=STORE,
        shopper_id=SHOPPER,
        session_id="s1",
        kind="purchase",
        payload={},
        embedding=weird,
    )
    assert result.anomalous is True


@pytest.mark.asyncio
async def test_revise_belief_create_path_writes_audit() -> None:
    result = await revise_belief(
        action="create",
        reason="3 leather product views",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Prefers leather over synthetic",
        category="style",
        confidence=0.6,
        evidence_episode_ids=[uuid.uuid4()],
    )
    assert result.confidence == 0.6
    assert result.status == "active"

    async with async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit).where(MemoryAudit.belief_id == result.belief_id)
            )
        ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].action == ACTION_CREATE


@pytest.mark.asyncio
async def test_revise_belief_create_requires_fields() -> None:
    with pytest.raises(ValueError):
        await revise_belief(action="create", reason="missing fields")


@pytest.mark.asyncio
async def test_revise_belief_reinforce_path_bumps_confidence() -> None:
    created = await revise_belief(
        action="create",
        reason="initial",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Budget conscious",
        category="budget",
        confidence=0.5,
    )

    reinforced = await revise_belief(
        action="reinforce",
        belief_id=created.belief_id,
        reason="another budget-conscious purchase",
        confidence=0.7,
        evidence_episode_ids=[uuid.uuid4()],
    )
    assert reinforced.belief_id == created.belief_id
    assert reinforced.confidence == 0.7

    async with async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit)
                .where(MemoryAudit.belief_id == created.belief_id)
                .order_by(MemoryAudit.created_at)
            )
        ).scalars().all()
    assert [row.action for row in audit_rows] == [ACTION_CREATE, ACTION_REINFORCE]


@pytest.mark.asyncio
async def test_revise_belief_decay_action_lowers_confidence_and_audits_as_decay() -> None:
    created = await revise_belief(
        action="create",
        reason="initial",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Likes premium brands",
        category="brand",
        confidence=0.5,
    )

    decayed = await revise_belief(
        action="decay",
        belief_id=created.belief_id,
        reason="confidence decayed to 0.2 after 90 days",
        confidence=0.2,
    )
    assert decayed.confidence == 0.2
    assert decayed.status == "decaying"

    async with async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit)
                .where(MemoryAudit.belief_id == created.belief_id)
                .order_by(MemoryAudit.created_at)
            )
        ).scalars().all()
    assert audit_rows[-1].action == ACTION_DECAY


@pytest.mark.asyncio
async def test_revise_belief_unknown_id_raises() -> None:
    with pytest.raises(ValueError):
        await revise_belief(
            action="revise", belief_id=uuid.uuid4(), reason="doesn't exist", confidence=0.1
        )


@pytest.mark.asyncio
async def test_forget_marks_deprecated_and_audits() -> None:
    created = await revise_belief(
        action="create",
        reason="initial",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Likes minimalist style",
        category="style",
        confidence=0.5,
    )

    result = await forget(created.belief_id, reason="shopper deleted it in the Inspector")
    assert result.status == "deprecated"

    async with async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit)
                .where(MemoryAudit.belief_id == created.belief_id)
                .order_by(MemoryAudit.created_at)
            )
        ).scalars().all()
    assert audit_rows[-1].action == "deprecate"


@pytest.mark.asyncio
async def test_forget_user_delete_action_is_audited_distinctly() -> None:
    created = await revise_belief(
        action="create",
        reason="initial",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Likes bold colors",
        category="style",
        confidence=0.5,
    )

    result = await forget(created.belief_id, reason="shopper clicked delete", action="user_delete")
    assert result.status == "deprecated"

    async with async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit)
                .where(MemoryAudit.belief_id == created.belief_id)
                .order_by(MemoryAudit.created_at)
            )
        ).scalars().all()
    assert audit_rows[-1].action == "user_delete"


@pytest.mark.asyncio
async def test_recall_ranks_by_query_embedding_similarity() -> None:
    leather_vec = _unit_vector(0)
    minimalist_vec = _unit_vector(4)

    await revise_belief(
        action="create",
        reason="init",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Prefers leather",
        category="style",
        confidence=0.5,
    )
    async with async_session() as session:
        from mcp_memory.models import Belief

        belief = (
            await session.execute(select(Belief).where(Belief.statement == "Prefers leather"))
        ).scalar_one()
        belief.embedding = leather_vec
        await session.commit()

    await revise_belief(
        action="create",
        reason="init",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="Prefers minimalist design",
        category="style",
        confidence=0.5,
    )
    async with async_session() as session:
        from mcp_memory.models import Belief

        belief = (
            await session.execute(
                select(Belief).where(Belief.statement == "Prefers minimalist design")
            )
        ).scalar_one()
        belief.embedding = minimalist_vec
        await session.commit()

    result = await recall(
        store_id=STORE,
        shopper_id=SHOPPER,
        query="leather bags",
        query_embedding=leather_vec,
        budget_tokens=1500,
    )
    assert result.beliefs[0].statement == "Prefers leather"


@pytest.mark.asyncio
async def test_recall_respects_budget_tokens() -> None:
    await revise_belief(
        action="create",
        reason="init",
        store_id=STORE,
        shopper_id=SHOPPER,
        statement="x" * 400,
        category="style",
        confidence=0.9,
    )
    result = await recall(store_id=STORE, shopper_id=SHOPPER, query="", budget_tokens=10)
    assert result.beliefs == []
    assert result.budget_used_tokens == 0
