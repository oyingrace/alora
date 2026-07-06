from typing import Literal

from pydantic import BaseModel, Field

EventKind = Literal["search", "view", "dwell", "add_to_cart", "purchase", "chat", "correction"]


class EventIn(BaseModel):
    store_id: str
    shopper_id: str
    session_id: str
    kind: EventKind
    payload: dict = Field(default_factory=dict)


class EventOut(BaseModel):
    episode_id: str
    needs_clarification: bool = False
