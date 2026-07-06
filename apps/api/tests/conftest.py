import pytest
import pytest_asyncio
import redis.asyncio as redis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.services.embeddings as embeddings_module
import app.services.session_store as session_store_module
from app import db as db_module
from app.core.config import get_settings
from app.main import app
from app.services.memory_client import memory_client


@pytest.fixture(autouse=True)
def _fresh_async_resources():
    """Recreate the Redis clients and SQLAlchemy engine for every test function.

    All are module-level singletons bound to whichever event loop first uses
    them — fine in production (one persistent loop for the app's lifetime), but
    this test session mixes pytest-asyncio's own loop (tests that `await` worker
    functions directly) with TestClient's separate portal-thread loop (tests that
    go through the HTTP app), so a binding from one style breaks the other.
    Callers must reach these through the module (`db.async_session()`,
    `embeddings_module._redis`) rather than via `from app.db import async_session`,
    which would capture the pre-fixture object instead of the fresh one.
    Cheap to recreate: neither connects until first use.
    """
    embeddings_module._redis = redis.from_url(
        get_settings().redis_url, decode_responses=True
    )
    session_store_module._redis = redis.from_url(
        get_settings().redis_url, decode_responses=True
    )
    db_module.engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    db_module.async_session = async_sessionmaker(db_module.engine, expire_on_commit=False)
    yield


@pytest.fixture(scope="module")
def client():
    """One TestClient (and one event loop) shared across a test module.

    The MCP client's stdio session and the module-level Redis client are both
    bound to whichever event loop first touches them; a fresh TestClient per test
    function spins up a new loop/thread each time and breaks that binding.
    """
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def connected_memory_client():
    """Connects the global `memory_client` singleton directly in the test's own
    asyncio loop, for tests that `await` worker functions (decay tick, consolidation)
    directly rather than going through `client: TestClient`.

    `TestClient` runs the ASGI app — and therefore `memory_client.connect()` — inside
    its own background thread/event loop (an anyio portal). A test that awaits
    `memory_client` calls directly runs in pytest-asyncio's loop instead, a different
    one; reusing a session opened on the portal's loop from here hangs rather than
    erroring, since anyio waits on a stream whose reader lives on a loop that's never
    scheduled to run it. Connecting here keeps everything on one loop.

    Deliberately no teardown: pytest-asyncio runs async-fixture finalizers via a
    fresh `runner.run()` call, which is a new anyio task even on the same loop, and
    anyio's stdio-client cancel scope can only be exited from the task that entered
    it. The subprocess this opens is reaped when the test process exits.
    """
    await memory_client.connect()
    return memory_client
