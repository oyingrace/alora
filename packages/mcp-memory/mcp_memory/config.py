from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://memora:memora@localhost:5432/memora"
    default_recall_budget_tokens: int = 1500


@lru_cache
def get_settings() -> Settings:
    return Settings()
