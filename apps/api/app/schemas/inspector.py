import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InspectorBelief(BaseModel):
    id: uuid.UUID
    statement: str
    category: str
    confidence: float
    status: str
    last_reinforced_at: datetime


class AuditEntry(BaseModel):
    id: uuid.UUID
    belief_id: uuid.UUID
    action: str
    reason: str
    created_at: datetime


class MemoryListOut(BaseModel):
    beliefs: list[InspectorBelief] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)


class ReviseBeliefIn(BaseModel):
    statement: str | None = None
    confidence: float | None = None
    reason: str
