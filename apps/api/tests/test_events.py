import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _unit_vector(hot_index: int, dim: int = 1024) -> list[float]:
    vec = [0.0] * dim
    vec[hot_index] = 1.0
    return vec


def test_post_event_normal_view(client: TestClient) -> None:
    with (
        patch(
            "app.services.intent.qwen.chat",
            new=AsyncMock(return_value='{"summary": "Viewed a leather bag", "intent": "self"}'),
        ),
        patch(
            "app.services.embeddings.qwen.embed",
            new=AsyncMock(return_value=[_unit_vector(0)]),
        ),
    ):
        response = client.post(
            "/events",
            json={
                "store_id": "demo",
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "session_id": "s1",
                "kind": "view",
                "payload": {"product_id": "p1"},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["episode_id"]
    assert body["needs_clarification"] is False


def test_purchase_anomaly_triggers_clarification(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    run_id = uuid.uuid4().hex
    normal_vec = _unit_vector(0)
    weird_vec = _unit_vector(7)

    chat_responses = [
        f'{{"summary": "Bought item {i} {run_id}", "intent": "unknown"}}' for i in range(5)
    ]
    embed_vectors = [[normal_vec]] * 4 + [[weird_vec]]

    with (
        patch("app.services.intent.qwen.chat", new=AsyncMock(side_effect=chat_responses)),
        patch(
            "app.services.embeddings.qwen.embed", new=AsyncMock(side_effect=embed_vectors)
        ),
    ):
        responses = [
            client.post(
                "/events",
                json={
                    "store_id": "demo",
                    "shopper_id": shopper_id,
                    "session_id": "s1",
                    "kind": "purchase",
                    "payload": {"product_id": f"p{i}"},
                },
            )
            for i in range(5)
        ]

    assert all(r.status_code == 200 for r in responses)
    assert responses[-1].json()["needs_clarification"] is True


def test_qwen_unavailable_still_persists_episode(client: TestClient) -> None:
    from app.services.qwen import QwenUnavailableError

    with (
        patch(
            "app.services.intent.qwen.chat",
            new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
        ),
        patch(
            "app.services.embeddings.qwen.embed",
            new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
        ),
    ):
        response = client.post(
            "/events",
            json={
                "store_id": "demo",
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "session_id": "s1",
                "kind": "view",
                "payload": {"product_id": "p1"},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["episode_id"]
    assert body["needs_clarification"] is False
