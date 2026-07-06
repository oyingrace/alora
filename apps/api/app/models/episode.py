import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EMBEDDING_DIM = 1024

# episodes.kind values
KIND_SEARCH = "search"
KIND_VIEW = "view"
KIND_DWELL = "dwell"
KIND_ADD_TO_CART = "add_to_cart"
KIND_PURCHASE = "purchase"
KIND_CHAT = "chat"
KIND_CORRECTION = "correction"

# episodes.intent values
INTENT_SELF = "self"
INTENT_GIFT = "gift"
INTENT_RESEARCH = "research"
INTENT_UNKNOWN = "unknown"


class Episode(Base):
    """Raw behavioral event — episodic memory."""

    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(String, index=True)
    shopper_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)

    kind: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    intent: Mapped[str] = mapped_column(String, default=INTENT_UNKNOWN)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
