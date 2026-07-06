import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app import db
from app.models import Episode
from app.models.autonomy import LEVEL_ASK_FIRST, LEVEL_AUTO_NOTIFY, LEVEL_RECOMMEND_ONLY
from app.models.episode import KIND_PURCHASE, KIND_REORDER
from app.services.autonomy import (
    detect_reorder_candidates,
    get_autonomy_status,
    record_reorder_decision,
    revoke_autonomy,
)
from app.services.chat_agent import run_chat

STORE = "demo"


def _tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


async def _seed_purchase(shopper_id: str, product_id: str, days_ago: float) -> None:
    async with db.async_session() as session:
        session.add(
            Episode(
                store_id=STORE,
                shopper_id=shopper_id,
                session_id="s1",
                kind=KIND_PURCHASE,
                payload={"product_id": product_id},
                intent="self",
                created_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_detect_candidates_ignores_single_purchase(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=40)

    candidates = await detect_reorder_candidates(STORE, shopper_id)
    assert candidates == []


@pytest.mark.asyncio
async def test_detect_candidates_ignores_not_yet_due(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    # Two purchases ~30 days apart, but the last one was just yesterday — not due yet.
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=31)
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=1)

    candidates = await detect_reorder_candidates(STORE, shopper_id)
    assert candidates == []


@pytest.mark.asyncio
async def test_detect_candidates_finds_overdue_cadence(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    # Purchased every ~30 days, and it's now been 35 days since the last one.
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=65)
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=35)

    candidates = await detect_reorder_candidates(STORE, shopper_id)
    assert len(candidates) == 1
    assert candidates[0].product_id == "coffee-pods"
    assert candidates[0].times_purchased == 2
    assert candidates[0].cadence_days == pytest.approx(30.0, abs=0.1)


@pytest.mark.asyncio
async def test_detect_candidates_considers_prior_reorders_too(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    await _seed_purchase(shopper_id, "coffee-pods", days_ago=65)
    async with db.async_session() as session:
        session.add(
            Episode(
                store_id=STORE,
                shopper_id=shopper_id,
                session_id="autonomy",
                kind=KIND_REORDER,
                payload={"product_id": "coffee-pods", "auto": False},
                intent="self",
                created_at=datetime.now(UTC) - timedelta(days=35),
            )
        )
        await session.commit()

    candidates = await detect_reorder_candidates(STORE, shopper_id)
    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_get_autonomy_status_defaults_to_ask_first(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    status = await get_autonomy_status(shopper_id)
    assert status.level == LEVEL_ASK_FIRST
    assert status.approvals == 0
    assert status.rejections == 0


@pytest.mark.asyncio
async def test_approve_increments_and_writes_reorder_episode(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    status = await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)

    assert status.approvals == 1
    assert status.level == LEVEL_ASK_FIRST
    assert status.promoted is False

    async with db.async_session() as session:
        rows = (
            await session.execute(
                select(Episode).where(
                    Episode.shopper_id == shopper_id, Episode.kind == KIND_REORDER
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["product_id"] == "coffee-pods"
    assert rows[0].payload["auto"] is False


@pytest.mark.asyncio
async def test_reject_increments_rejections_without_episode(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    status = await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=False)

    assert status.rejections == 1
    assert status.approvals == 0

    async with db.async_session() as session:
        rows = (
            await session.execute(
                select(Episode).where(
                    Episode.shopper_id == shopper_id, Episode.kind == KIND_REORDER
                )
            )
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_promotes_to_auto_notify_after_three_approvals(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"

    first = await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)
    assert first.level == LEVEL_ASK_FIRST
    assert first.promoted is False

    second = await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)
    assert second.level == LEVEL_ASK_FIRST
    assert second.promoted is False

    third = await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)
    assert third.level == LEVEL_AUTO_NOTIFY
    assert third.promoted is True
    assert third.approvals == 3


@pytest.mark.asyncio
async def test_revoke_resets_to_recommend_only(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    for _ in range(3):
        await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)

    status_before = await get_autonomy_status(shopper_id)
    assert status_before.level == LEVEL_AUTO_NOTIFY

    revoked = await revoke_autonomy(shopper_id)
    assert revoked.level == LEVEL_RECOMMEND_ONLY
    # approvals/rejections history isn't wiped, just the level
    assert revoked.approvals == 3

    status_after = await get_autonomy_status(shopper_id)
    assert status_after.level == LEVEL_RECOMMEND_ONLY


@pytest.mark.asyncio
async def test_revoke_unknown_shopper_is_a_noop(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    status = await revoke_autonomy(shopper_id)
    assert status.level == LEVEL_RECOMMEND_ONLY


@pytest.mark.asyncio
async def test_chat_create_reorder_proposal_needs_approval_at_ask_first(
    connected_memory_client,
) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    first = _message(
        content=None,
        tool_calls=[
            _tool_call("call_1", "create_reorder_proposal", '{"product_id": "coffee-pods"}')
        ],
    )
    second = _message(content="Want me to reorder your coffee pods?")

    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(side_effect=[first, second]),
    ):
        reply, degraded = await run_chat(
            store_id=STORE, shopper_id=shopper_id, session_id="s1", message="reorder my coffee"
        )

    assert degraded is False
    assert "reorder" in reply.lower()


@pytest.mark.asyncio
async def test_chat_create_reorder_proposal_auto_reorders_at_level_two(
    connected_memory_client,
) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    for _ in range(3):
        await record_reorder_decision(STORE, shopper_id, "coffee-pods", approve=True)

    first = _message(
        content=None,
        tool_calls=[
            _tool_call("call_1", "create_reorder_proposal", '{"product_id": "coffee-pods"}')
        ],
    )
    second = _message(content="Done — I've already reordered your coffee pods!")

    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(side_effect=[first, second]),
    ):
        reply, degraded = await run_chat(
            store_id=STORE, shopper_id=shopper_id, session_id="s1", message="reorder my coffee"
        )

    assert degraded is False

    async with db.async_session() as session:
        rows = (
            await session.execute(
                select(Episode).where(
                    Episode.shopper_id == shopper_id, Episode.kind == KIND_REORDER
                )
            )
        ).scalars().all()
    # 3 from the approvals loop + 1 from the auto-reorder tool call
    assert len(rows) == 4
    assert rows[-1].payload["auto"] is True


@pytest.mark.asyncio
async def test_chat_create_reorder_proposal_declines_for_anonymous_shopper(
    connected_memory_client,
) -> None:
    first = _message(
        content=None,
        tool_calls=[
            _tool_call("call_1", "create_reorder_proposal", '{"product_id": "coffee-pods"}')
        ],
    )
    second = _message(content="I can't set up reorders while you're browsing anonymously.")

    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(side_effect=[first, second]),
    ):
        reply, degraded = await run_chat(
            store_id=STORE,
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id=f"session-{uuid.uuid4().hex}",
            message="reorder my coffee",
            persist=False,
        )

    assert degraded is False
    assert "anonymous" in reply.lower() or "anonymously" in reply.lower()
