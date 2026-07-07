from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The one shared .env lives at the repo root (docker-compose's services also point
# at it via `env_file: ../.env`). pydantic-settings resolves a relative env_file
# against the current working directory, not this file's location — and both
# `make dev` and running scripts by hand commonly `cd apps/api` first — so this
# must be an absolute path or it silently finds nothing and falls back to defaults.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """All config from environment. Never hardcode model names or secrets elsewhere."""

    model_config = SettingsConfigDict(env_file=_REPO_ROOT / ".env", extra="ignore")

    # Qwen Cloud
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    model_reasoning: str = "qwen-max"
    model_fast: str = "qwen-turbo"
    model_vision: str = "qwen-vl-max"
    model_embed: str = "text-embedding-v3"

    # Postgres
    database_url: str = "postgresql+asyncpg://memora:memora@localhost:5432/memora"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    environment: str = "development"
    log_level: str = "info"

    # Memory
    recall_budget_tokens: int = 1500
    consolidation_every_n_events: int = 15
    decay_tick_interval_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
