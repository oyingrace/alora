from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://memora:memora@localhost:5432/memora"
    default_recall_budget_tokens: int = 1500

    # Anomaly detection for the gift-clarification flow (BUILD_PLAN.md §5.2 step 1)
    anomaly_similarity_threshold: float = 0.55
    anomaly_min_purchase_history: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
