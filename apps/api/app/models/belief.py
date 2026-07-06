import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.episode import EMBEDDING_DIM

# beliefs.category values
CATEGORY_STYLE = "style"
CATEGORY_BUDGET = "budget"
CATEGORY_SIZE = "size"
CATEGORY_BRAND = "brand"
CATEGORY_CADENCE = "cadence"
CATEGORY_CONSTRAINT = "constraint"

# per-category decay half-life, in days (BUILD_PLAN §5.1)
DECAY_HALF_LIFE_DAYS: dict[str, int] = {
    CATEGORY_BUDGET: 30,
    CATEGORY_STYLE: 90,
    CATEGORY_SIZE: 365,
    CATEGORY_BRAND: 90,
    CATEGORY_CADENCE: 60,
    CATEGORY_CONSTRAINT: 180,
}
DEFAULT_HALF_LIFE_DAYS = 90

# beliefs.status values
STATUS_ACTIVE = "active"
STATUS_DECAYING = "decaying"
STATUS_DEPRECATED = "deprecated"

DECAYING_THRESHOLD = 0.3
DEPRECATED_THRESHOLD = 0.15


class Belief(Base):
    """Consolidated, provenance-carrying belief — semantic memory."""

    __tablename__ = "beliefs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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
    decay_half_life_days: Mapped[int] = mapped_column(Integer, default=DEFAULT_HALF_LIFE_DAYS)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
