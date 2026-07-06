from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatIn(BaseModel):
    store_id: str
    shopper_id: str
    session_id: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    # From the consent banner (CLAUDE.md architecture rule 5): False means the
    # shopper stays anonymous — Redis session memory with TTL only, never Postgres.
    persist: bool = True


class ChatOut(BaseModel):
    reply: str
    degraded: bool = False
