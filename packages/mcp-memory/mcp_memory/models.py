"""Mirrors the tables owned by apps/api/app/models — same Postgres database, read/write
access scoped to exactly what the four MCP tools need. This package intentionally does
not import from apps/api so it stays a standalone, mountable component.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, JSON, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from mcp_memory.db import Base

EMBEDDING_DIM = 1024

STATUS_ACTIVE = "active"
STATUS_DECAYING = "decaying"
STATUS_DEPRECATED = "deprecated"

# confidence thresholds for status transitions (BUILD_PLAN.md §5.2 decay step)
DECAYING_THRESHOLD = 0.3
DEPRECATED_THRESHOLD = 0.15

# per-category decay half-life, in days (BUILD_PLAN.md §5.1)
DECAY_HALF_LIFE_DAYS: dict[str, int] = {
    "budget": 30,
    "style": 90,
    "size": 365,
    "brand": 90,
    "cadence": 60,
    "constraint": 180,
}
DEFAULT_HALF_LIFE_DAYS = 90

ACTION_CREATE = "create"
ACTION_REINFORCE = "reinforce"
ACTION_REVISE = "revise"
ACTION_DECAY = "decay"
ACTION_DEPRECATE = "deprecate"
ACTION_USER_DELETE = "user_delete"


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String, index=True)
    shopper_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    intent: Mapped[str] = mapped_column(String, default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Belief(Base):
    __tablename__ = "beliefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String, index=True)
    shopper_id: Mapped[str] = mapped_column(String, index=True)
    statement: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    status: Mapped[str] = mapped_column(String, default=STATUS_ACTIVE, index=True)
    last_reinforced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decay_half_life_days: Mapped[int] = mapped_column(Integer, default=90)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryAudit(Base):
    __tablename__ = "memory_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    belief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    shopper_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
