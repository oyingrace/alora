import uuid

import pytest

from app.services.memory_client import MemoryClient, MemoryToolError


@pytest.mark.asyncio
async def test_write_episode_and_recall_round_trip() -> None:
    client = MemoryClient()
    await client.connect()
    try:
        write_result = await client.write_episode(
            store_id="demo",
            shopper_id="shopper-test",
            session_id="s1",
            kind="view",
            payload={"product_id": "p1"},
            summary="Viewed a leather bag",
            intent="self",
        )
        assert write_result.episode_id is not None
        assert write_result.anomalous is False

        recall_result = await client.recall(
            store_id="demo", shopper_id="shopper-test", query="bags"
        )
        assert any(e.summary == "Viewed a leather bag" for e in recall_result.episodes)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_revise_belief_create_then_forget() -> None:
    client = MemoryClient()
    await client.connect()
    try:
        created = await client.revise_belief(
            action="create",
            reason="test create",
            store_id="demo",
            shopper_id="shopper-test",
            statement="Prefers minimalist style",
            category="style",
            confidence=0.6,
        )
        assert created.confidence == 0.6

        forgotten = await client.forget(created.belief_id, reason="test forget")
        assert forgotten.status == "deprecated"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_forget_unknown_belief_raises_tool_error_not_unavailable() -> None:
    """MemoryToolError (tool rejected the call) must be distinguishable from
    MemoryUnavailableError (transport failure) — a not-found belief is the former.
    """
    client = MemoryClient()
    await client.connect()
    try:
        with pytest.raises(MemoryToolError):
            await client.forget(uuid.uuid4(), reason="doesn't exist")
    finally:
        await client.close()
