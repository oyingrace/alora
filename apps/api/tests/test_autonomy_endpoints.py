import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

STORE = "demo"


def _seed_purchases(shopper_id: str, product_id: str, days_ago_list: list[float]) -> None:
    """Isolated throwaway-loop seeding — see tests/test_memory_inspector.py for why."""
    from app.models import Episode
    from app.models.episode import KIND_PURCHASE

    async def _do() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            for days_ago in days_ago_list:
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
        await engine.dispose()

    asyncio.run(_do())


def test_autonomy_status_defaults_to_ask_first(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    response = client.get("/autonomy", params={"shopper_id": shopper_id})
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == 1
    assert body["approvals"] == 0


def test_reorder_candidates_endpoint(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    _seed_purchases(shopper_id, "coffee-pods", [65, 35])

    response = client.get(
        "/autonomy/reorder/candidates", params={"store_id": STORE, "shopper_id": shopper_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["product_id"] == "coffee-pods"


def test_reorder_decide_endpoint_approve(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    response = client.post(
        "/autonomy/reorder/decide",
        json={
            "store_id": STORE,
            "shopper_id": shopper_id,
            "product_id": "coffee-pods",
            "approve": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approvals"] == 1
    assert body["level"] == 1


def test_revoke_endpoint(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    client.post(
        "/autonomy/reorder/decide",
        json={
            "store_id": STORE,
            "shopper_id": shopper_id,
            "product_id": "coffee-pods",
            "approve": True,
        },
    )

    response = client.post("/autonomy/revoke", json={"shopper_id": shopper_id})
    assert response.status_code == 200
    assert response.json()["level"] == 0
