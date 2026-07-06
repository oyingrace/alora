import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.chat_agent import run_chat


def _tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _vec(hot_index: int, dim: int = 1024) -> list[float]:
    v = [0.0] * dim
    v[hot_index] = 1.0
    return v


@pytest.mark.asyncio
async def test_chat_direct_reply_without_tool_calls(connected_memory_client) -> None:
    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(return_value=_message(content="Hi there!")),
    ):
        reply, degraded = await run_chat(
            store_id="demo",
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id="s1",
            message="hello",
        )

    assert reply == "Hi there!"
    assert degraded is False


@pytest.mark.asyncio
async def test_chat_uses_recall_tool_then_replies(connected_memory_client) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"

    first = _message(
        content=None,
        tool_calls=[_tool_call("call_1", "recall", '{"query": "bag preferences"}')],
    )
    second = _message(content="You seem to like leather bags!")

    with (
        patch(
            "app.services.chat_agent.qwen.chat_message",
            new=AsyncMock(side_effect=[first, second]),
        ),
        patch(
            "app.services.chat_agent.embed_cached",
            new=AsyncMock(return_value=_vec(0)),
        ),
    ):
        reply, degraded = await run_chat(
            store_id="demo", shopper_id=shopper_id, session_id="s1", message="what do I like?"
        )

    assert reply == "You seem to like leather bags!"
    assert degraded is False


@pytest.mark.asyncio
async def test_chat_uses_catalog_search_tool(connected_memory_client) -> None:
    from app import db
    from app.models import Product

    store_id = f"store-{uuid.uuid4().hex}"
    async with db.async_session() as session:
        session.add(
            Product(
                store_id=store_id,
                external_id="p1",
                name="Leather Tote",
                description="",
                category="bags",
                price=100.0,
                currency="USD",
                tags={},
                embedding=_vec(0),
            )
        )
        await session.commit()

    first = _message(
        content=None,
        tool_calls=[_tool_call("call_1", "catalog_search", '{"query": "leather bag"}')],
    )
    second = _message(content="I found a Leather Tote for $100.")

    with (
        patch(
            "app.services.chat_agent.qwen.chat_message",
            new=AsyncMock(side_effect=[first, second]),
        ),
        patch(
            "app.services.chat_agent.embed_cached",
            new=AsyncMock(return_value=_vec(0)),
        ),
    ):
        reply, degraded = await run_chat(
            store_id=store_id,
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id="s1",
            message="find me a leather bag",
        )

    assert "Leather Tote" in reply
    assert degraded is False


@pytest.mark.asyncio
async def test_chat_degrades_honestly_when_qwen_unavailable(connected_memory_client) -> None:
    from app.services.qwen import QwenUnavailableError

    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
    ):
        reply, degraded = await run_chat(
            store_id="demo",
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id="s1",
            message="hello",
        )

    assert degraded is True
    assert "offline" in reply.lower()


@pytest.mark.asyncio
async def test_chat_falls_back_when_tool_loop_never_resolves(connected_memory_client) -> None:
    looping_message = _message(
        content=None,
        tool_calls=[_tool_call("call_1", "recall", '{"query": "x"}')],
    )

    with (
        patch(
            "app.services.chat_agent.qwen.chat_message",
            new=AsyncMock(return_value=looping_message),
        ),
        patch(
            "app.services.chat_agent.embed_cached",
            new=AsyncMock(return_value=_vec(0)),
        ),
    ):
        reply, degraded = await run_chat(
            store_id="demo",
            shopper_id=f"shopper-{uuid.uuid4().hex}",
            session_id="s1",
            message="loop forever",
        )

    assert degraded is False
    assert "trouble" in reply.lower()


def test_chat_endpoint_returns_reply(client: TestClient) -> None:
    with patch(
        "app.services.chat_agent.qwen.chat_message",
        new=AsyncMock(return_value=_message(content="Hi there!")),
    ):
        response = client.post(
            "/chat",
            json={
                "store_id": "demo",
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "session_id": "s1",
                "message": "hello",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hi there!"
    assert body["degraded"] is False
