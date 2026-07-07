import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import session_store
from app.services.chat_agent import _run_recall, run_chat


@pytest.mark.asyncio
async def test_append_and_get_events_round_trip() -> None:
    session_id = f"session-{uuid.uuid4().hex}"

    await session_store.append_event(session_id, "view", {"product_id": "p1"})
    await session_store.append_event(session_id, "add_to_cart", {"product_id": "p1"})

    events = await session_store.get_events(session_id)
    assert [e["kind"] for e in events] == ["view", "add_to_cart"]
    assert events[0]["payload"] == {"product_id": "p1"}


@pytest.mark.asyncio
async def test_get_events_empty_for_unknown_session() -> None:
    events = await session_store.get_events(f"session-{uuid.uuid4().hex}")
    assert events == []


@pytest.mark.asyncio
async def test_events_trimmed_to_max_length() -> None:
    session_id = f"session-{uuid.uuid4().hex}"
    for i in range(session_store._MAX_EVENTS + 10):
        await session_store.append_event(session_id, "view", {"i": i})

    events = await session_store.get_events(session_id)
    assert len(events) == session_store._MAX_EVENTS
    # oldest events were dropped, newest kept
    assert events[-1]["payload"]["i"] == session_store._MAX_EVENTS + 9


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


@pytest.mark.asyncio
async def test_chat_anonymous_session_skips_mcp_and_uses_session_store(
    connected_memory_client,
) -> None:
    """persist=False must never call memory_client.write_episode; the exchange
    goes to the ephemeral Redis session store instead (architecture rule 5).
    """
    session_id = f"session-{uuid.uuid4().hex}"

    with (
        patch(
            "app.services.chat_agent.qwen.chat_message",
            new=AsyncMock(return_value=_message(content="Sure, happy to help anonymously!")),
        ),
        patch(
            "app.services.chat_agent.memory_client.write_episode", new=AsyncMock()
        ) as mock_write_episode,
    ):
        reply, degraded = await run_chat(
            store_id="demo",
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id=session_id,
            message="hello anonymously",
            persist=False,
        )

    assert reply == "Sure, happy to help anonymously!"
    assert degraded is False
    mock_write_episode.assert_not_awaited()

    events = await session_store.get_events(session_id)
    assert len(events) == 1
    assert events[0]["kind"] == "chat"


@pytest.mark.asyncio
async def test_anonymous_recall_surfaces_this_session_own_chat_content() -> None:
    """The recall tool must be able to answer "did I already ask about X" within
    a single anonymous session — it's the session's own ephemeral data, so there's
    no privacy reason to hide it, unlike a real cross-session persisted belief.
    """
    session_id = f"session-{uuid.uuid4().hex}"
    await session_store.append_event(
        session_id, "chat", {"message": "how much are the canvas sneakers?", "reply": "$32"}
    )

    result = await _run_recall(
        store_id="demo",
        shopper_id="anon",
        session_id=session_id,
        query="sneakers",
        persist=False,
    )

    assert result["beliefs"] == []
    assert result["recent_activity"] == [
        {"kind": "chat", "summary": "asked: how much are the canvas sneakers?"}
    ]
