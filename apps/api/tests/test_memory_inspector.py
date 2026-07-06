import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def _seed_belief(store_id: str, shopper_id: str, **overrides) -> uuid.UUID:
    """Seeds a belief via a fully isolated, throwaway event loop (its own engine,
    NullPool, closed immediately after) — never the shared `app.db` engine, so it
    can't collide with whichever loop `client: TestClient`'s portal thread uses.
    """
    from app.models import Belief

    defaults = dict(
        store_id=store_id,
        shopper_id=shopper_id,
        statement="Prefers leather over synthetic",
        category="style",
        confidence=0.6,
        evidence=[],
    )
    defaults.update(overrides)

    async def _do() -> uuid.UUID:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            belief = Belief(**defaults)
            session.add(belief)
            await session.commit()
            belief_id = belief.id
        await engine.dispose()
        return belief_id

    return asyncio.run(_do())


def _seed_audit(belief_id: uuid.UUID, store_id: str, shopper_id: str, action: str, reason: str) -> None:
    from app.models import MemoryAudit

    async def _do() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            session.add(
                MemoryAudit(
                    belief_id=belief_id, store_id=store_id, shopper_id=shopper_id,
                    action=action, reason=reason,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_do())


def test_no_post_endpoint_on_memory(client: TestClient) -> None:
    # Beliefs are only ever created by the consolidation worker, never directly.
    response = client.post("/memory", json={})
    assert response.status_code == 405


def test_inspector_list_is_empty_for_unknown_shopper(client: TestClient) -> None:
    response = client.get(
        "/memory", params={"store_id": "demo", "shopper_id": f"shopper-{uuid.uuid4().hex}"}
    )
    assert response.status_code == 200
    assert response.json() == {"beliefs": [], "audit": []}


def test_inspector_shows_belief_and_audit(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    belief_id = _seed_belief("demo", shopper_id)
    _seed_audit(belief_id, "demo", shopper_id, action="create", reason="3 leather views")

    response = client.get("/memory", params={"store_id": "demo", "shopper_id": shopper_id})

    assert response.status_code == 200
    body = response.json()
    assert len(body["beliefs"]) == 1
    assert body["beliefs"][0]["statement"] == "Prefers leather over synthetic"
    assert len(body["audit"]) == 1
    assert body["audit"][0]["action"] == "create"


def test_correct_belief_via_patch(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    belief_id = _seed_belief("demo", shopper_id, category="budget", confidence=0.5)

    response = client.patch(
        f"/memory/{belief_id}",
        json={"confidence": 0.8, "reason": "shopper confirmed in the Inspector"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == 0.8
    assert body["belief_id"] == str(belief_id)


def test_delete_belief_via_delete(client: TestClient) -> None:
    shopper_id = f"shopper-{uuid.uuid4().hex}"
    belief_id = _seed_belief("demo", shopper_id)

    response = client.delete(f"/memory/{belief_id}", params={"reason": "shopper deleted it"})

    assert response.status_code == 200
    assert response.json()["status"] == "deprecated"

    audit_response = client.get("/memory", params={"store_id": "demo", "shopper_id": shopper_id})
    audit_actions = [a["action"] for a in audit_response.json()["audit"]]
    assert "user_delete" in audit_actions


def test_patch_unknown_belief_returns_404(client: TestClient) -> None:
    response = client.patch(f"/memory/{uuid.uuid4()}", json={"confidence": 0.5, "reason": "test"})
    assert response.status_code == 404


def test_delete_unknown_belief_returns_404(client: TestClient) -> None:
    response = client.delete(f"/memory/{uuid.uuid4()}", params={"reason": "test"})
    assert response.status_code == 404
