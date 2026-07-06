from pydantic import BaseModel, Field


class ProductIn(BaseModel):
    external_id: str
    name: str
    description: str = ""
    category: str = ""
    price: float = 0.0
    currency: str = "USD"
    image_url: str | None = None


class CatalogSyncIn(BaseModel):
    store_id: str
    products: list[ProductIn] = Field(default_factory=list)


class CatalogSyncOut(BaseModel):
    synced: int
