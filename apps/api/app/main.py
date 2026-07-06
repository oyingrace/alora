import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import catalog, chat, events, health, memory, recs
from app.services.memory_client import memory_client
from app.workers.decay import run_decay_tick

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("memora.main")


async def _decay_loop() -> None:
    while True:
        await asyncio.sleep(settings.decay_tick_interval_seconds)
        try:
            updated = await run_decay_tick()
            logger.info("decay tick: %d beliefs updated", updated)
        except Exception:  # noqa: BLE001 - a bad tick must never kill the loop
            logger.exception("decay tick failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await memory_client.connect()
    decay_task = asyncio.create_task(_decay_loop())
    try:
        yield
    finally:
        decay_task.cancel()
        await memory_client.close()


app = FastAPI(title="Memora API", version="0.1.0", lifespan=lifespan)

# The snippet is a script tag dropped onto arbitrary third-party storefronts, so
# its origin can't be known in advance — allow any origin. No cookies/credentials
# are used (shopper/session ids travel in the request body), so a wildcard is safe.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(recs.router)
