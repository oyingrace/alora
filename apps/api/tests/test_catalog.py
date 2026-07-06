import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.services.catalog import search_products


def _unit_vector(hot_index: int, dim: int = 1024) -> list[float]:
    vec = [0.0] * dim
    vec[hot_index] = 1.0
    return vec


def test_sync_catalog_upserts_products(client: TestClient) -> None:
    store_id = f"store-{uuid.uuid4().hex}"
    with patch(
        "app.services.embeddings.qwen.embed", new=AsyncMock(return_value=[_unit_vector(0)])
    ):
        response = client.post(
            "/catalog",
            json={
                "store_id": store_id,
                "products": [
                    {
                        "external_id": "p1",
                        "name": "Leather Tote",
                        "description": "A nice bag",
                        "category": "bags",
                        "price": 100.0,
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["synced"] == 1

    # re-sync (update path) with a different mocked embedding
    with patch(
        "app.services.embeddings.qwen.embed", new=AsyncMock(return_value=[_unit_vector(1)])
    ):
        response2 = client.post(
            "/catalog",
            json={
                "store_id": store_id,
                "products": [
                    {
                        "external_id": "p1",
                        "name": "Leather Tote (updated)",
                        "description": "A nice bag",
                        "category": "bags",
                        "price": 120.0,
                    }
                ],
            },
        )
    assert response2.status_code == 200


def test_sync_catalog_survives_qwen_outage(client: TestClient) -> None:
    from app.services.qwen import QwenUnavailableError

    store_id = f"store-{uuid.uuid4().hex}"
    with patch(
        "app.services.embeddings.qwen.embed",
        new=AsyncMock(side_effect=QwenUnavailableError("simulated outage")),
    ):
        response = client.post(
            "/catalog",
            json={
                "store_id": store_id,
                "products": [{"external_id": "p1", "name": "Some product"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["synced"] == 1


async def test_search_products_ranks_by_similarity() -> None:
    from app import db
    from app.models import Product

    store_id = f"store-{uuid.uuid4().hex}"
    leather_vec = _unit_vector(0)
    minimalist_vec = _unit_vector(4)

    async with db.async_session() as session:
        session.add_all(
            [
                Product(
                    store_id=store_id,
                    external_id="p1",
                    name="Leather Tote",
                    description="",
                    category="bags",
                    price=100.0,
                    currency="USD",
                    tags={},
                    embedding=leather_vec,
                ),
                Product(
                    store_id=store_id,
                    external_id="p2",
                    name="Minimalist Table",
                    description="",
                    category="furniture",
                    price=200.0,
                    currency="USD",
                    tags={},
                    embedding=minimalist_vec,
                ),
            ]
        )
        await session.commit()

    results = await search_products(store_id, query_embedding=leather_vec, limit=5)
    assert results[0].name == "Leather Tote"


async def test_search_products_filters_by_max_price() -> None:
    from app import db
    from app.models import Product

    store_id = f"store-{uuid.uuid4().hex}"
    async with db.async_session() as session:
        session.add_all(
            [
                Product(
                    store_id=store_id,
                    external_id="cheap",
                    name="Budget Sneakers",
                    description="",
                    category="shoes",
                    price=30.0,
                    currency="USD",
                    tags={},
                ),
                Product(
                    store_id=store_id,
                    external_id="expensive",
                    name="Premium Sneakers",
                    description="",
                    category="shoes",
                    price=300.0,
                    currency="USD",
                    tags={},
                ),
            ]
        )
        await session.commit()

    results = await search_products(store_id, query_embedding=None, max_price=50.0)
    names = {r.name for r in results}
    assert names == {"Budget Sneakers"}
