from pydantic import BaseModel, Field


class RecOut(BaseModel):
    name: str
    category: str
    price: float
    currency: str


class RecsOut(BaseModel):
    recommendations: list[RecOut] = Field(default_factory=list)
    degraded: bool = False
