import asyncio
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def _vec(hot_index: int, dim: int = 1024) -> list[float]:
    v = [0.0] * dim
    v[hot_index] = 1.0
    return v


def _seed_product(store_id: str, **overrides) -> None:
    """Seeds a product via a fully isolated throwaway event loop (own engine,
    NullPool) — see tests/test_memory_inspector.py for why this avoids the
    cross-loop hazard of mixing with `client: TestClient`'s portal loop.
    """
    from app.models import Product

    defaults = dict(
        store_id=store_id,
        external_id=f"p-{uuid.uuid4().hex}",
        name="Leather Tote",
        description="",
        category="bags",
        price=100.0,
        currency="USD",
        tags={},
        embedding=None,
    )
    defaults.update(overrides)

    async def _do() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            session.add(Product(**defaults))
            await session.commit()
        await engine.dispose()

    asyncio.run(_do())


def test_recs_falls_back_to_similarity_when_qwen_unavailable(client: TestClient) -> None:
    from app.services.qwen import QwenUnavailableError

    store_id = f"store-{uuid.uuid4().hex}"
    _seed_product(store_id, name="Leather Tote", embedding=_vec(0))

    with (
        patch(
            "app.services.embeddings.qwen.embed",
            new=AsyncMock(return_value=[_vec(0)]),
        ),
        patch(
            "app.services.recs.qwen.chat",
            new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
        ),
    ):
        response = client.get(
            "/recs",
            params={
                "store_id": store_id,
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "query": "leather bag",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert any(r["name"] == "Leather Tote" for r in body["recommendations"])


def test_recs_applies_qwen_reranking(client: TestClient) -> None:
    store_id = f"store-{uuid.uuid4().hex}"
    _seed_product(store_id, name="Budget Sneakers", price=30.0, embedding=_vec(0))
    _seed_product(store_id, name="Premium Sneakers", price=300.0, embedding=_vec(0))

    rerank_json = '{"rankings": [{"name": "Budget Sneakers", "score": 0.9}, {"name": "Premium Sneakers", "score": 0.4}]}'

    with (
        patch(
            "app.services.embeddings.qwen.embed",
            new=AsyncMock(return_value=[_vec(0)]),
        ),
        patch(
            "app.services.recs.qwen.chat",
            new=AsyncMock(return_value=rerank_json),
        ),
    ):
        response = client.get(
            "/recs",
            params={
                "store_id": store_id,
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "query": "sneakers",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is False
    names = [r["name"] for r in body["recommendations"]]
    assert names[0] == "Budget Sneakers"


def test_recs_filters_by_max_price(client: TestClient) -> None:
    store_id = f"store-{uuid.uuid4().hex}"
    _seed_product(store_id, name="Cheap Item", price=20.0)
    _seed_product(store_id, name="Expensive Item", price=500.0)

    with patch(
        "app.services.recs.qwen.chat", new=AsyncMock(return_value='{"rankings": []}')
    ):
        response = client.get(
            "/recs",
            params={
                "store_id": store_id,
                "shopper_id": f"shopper-{uuid.uuid4().hex}",
                "max_price": 50.0,
            },
        )

    assert response.status_code == 200
    names = {r["name"] for r in response.json()["recommendations"]}
    assert names == {"Cheap Item"}


def test_recs_empty_catalog_returns_no_recommendations(client: TestClient) -> None:
    store_id = f"store-{uuid.uuid4().hex}"
    response = client.get(
        "/recs", params={"store_id": store_id, "shopper_id": f"shopper-{uuid.uuid4().hex}"}
    )
    assert response.status_code == 200
    assert response.json() == {"recommendations": [], "degraded": False}
