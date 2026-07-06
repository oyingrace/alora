import pytest_asyncio
from sqlalchemy import text

from mcp_memory.db import async_session


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    async with async_session() as session:
        await session.execute(text("TRUNCATE episodes, beliefs, memory_audit CASCADE"))
        await session.commit()
    yield
