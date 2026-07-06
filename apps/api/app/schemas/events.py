from typing import Literal

from pydantic import BaseModel, Field

EventKind = Literal["search", "view", "dwell", "add_to_cart", "purchase", "chat", "correction"]


class EventIn(BaseModel):
    store_id: str
    shopper_id: str
    session_id: str
    kind: EventKind
    payload: dict = Field(default_factory=dict)
    # From the consent banner (CLAUDE.md architecture rule 5): False means the
    # shopper stays anonymous — Redis session memory with TTL only, never Postgres.
    persist: bool = True


class EventOut(BaseModel):
    episode_id: str
    needs_clarification: bool = False
