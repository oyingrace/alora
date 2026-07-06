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


class ChatOut(BaseModel):
    reply: str
    degraded: bool = False
