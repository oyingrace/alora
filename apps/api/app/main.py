import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import health

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(title="Memora API", version="0.1.0")

app.include_router(health.router)
