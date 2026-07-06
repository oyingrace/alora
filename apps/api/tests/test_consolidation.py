import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app import db
from app.models import Belief, MemoryAudit
from app.services.memory_client import memory_client
from app.workers.consolidation import consolidate_shopper


@pytest.mark.asyncio
async def test_consolidate_shopper_applies_create_mutation(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    await memory_client.write_episode(
        store_id="demo",
        shopper_id=shopper_id,
        session_id="s1",
        kind="view",
        payload={"product_id": "p1"},
        summary="Viewed three leather bags in a row",
        intent="self",
    )

    mutation_json = (
        '{"mutations": [{"action": "create", "statement": "Prefers leather", '
        '"category": "style", "confidence": 0.6, "evidence_episode_ids": [], '
        '"reason": "3 leather product views"}]}'
    )
    with patch(
        "app.workers.consolidation.qwen.chat", new=AsyncMock(return_value=mutation_json)
    ) as mock_chat:
        response = await consolidate_shopper("demo", shopper_id)

    mock_chat.assert_awaited_once()
    assert len(response.mutations) == 1

    async with db.async_session() as session:
        beliefs = (
            await session.execute(
                select(Belief).where(
                    Belief.store_id == "demo",
                    Belief.shopper_id == shopper_id,
                    Belief.statement == "Prefers leather",
                )
            )
        ).scalars().all()
    assert len(beliefs) == 1

    async with db.async_session() as session:
        audit_rows = (
            await session.execute(
                select(MemoryAudit).where(MemoryAudit.belief_id == beliefs[0].id)
            )
        ).scalars().all()
    assert audit_rows[0].action == "create"


@pytest.mark.asyncio
async def test_consolidate_shopper_no_episodes_skips_qwen_call(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    with patch("app.workers.consolidation.qwen.chat", new=AsyncMock()) as mock_chat:
        response = await consolidate_shopper("demo", shopper_id)

    mock_chat.assert_not_awaited()
    assert response.mutations == []


@pytest.mark.asyncio
async def test_consolidate_shopper_retries_once_on_invalid_json(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    await memory_client.write_episode(
        store_id="demo",
        shopper_id=shopper_id,
        session_id="s1",
        kind="view",
        payload={},
        summary="Viewed a product",
        intent="self",
    )

    valid_json = '{"mutations": []}'
    with patch(
        "app.workers.consolidation.qwen.chat",
        new=AsyncMock(side_effect=["not json", valid_json]),
    ) as mock_chat:
        response = await consolidate_shopper("demo", shopper_id)

    assert mock_chat.await_count == 2
    assert response.mutations == []


@pytest.mark.asyncio
async def test_consolidate_shopper_qwen_unavailable_returns_empty(connected_memory_client) -> None:
    from app.services.qwen import QwenUnavailableError

    shopper_id = f"shopper-{uuid.uuid4().hex}"
    await memory_client.write_episode(
        store_id="demo",
        shopper_id=shopper_id,
        session_id="s1",
        kind="view",
        payload={},
        summary="Viewed a product",
        intent="self",
    )

    with patch(
        "app.workers.consolidation.qwen.chat",
        new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
    ):
        response = await consolidate_shopper("demo", shopper_id)

    assert response.mutations == []
