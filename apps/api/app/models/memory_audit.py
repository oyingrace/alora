import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# memory_audit.action values — every belief mutation writes one row (CLAUDE.md rule 2)
ACTION_CREATE = "create"
ACTION_REINFORCE = "reinforce"
ACTION_REVISE = "revise"
ACTION_DEPRECATE = "deprecate"
ACTION_USER_DELETE = "user_delete"


class MemoryAudit(Base):
    """Human-readable log of every belief mutation. Rendered verbatim in the Inspector."""

    __tablename__ = "memory_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    belief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    shopper_id: Mapped[str] = mapped_column(String, index=True)

    action: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
