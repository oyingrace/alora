"""Typed views of packages/mcp-memory's tool results, kept independently here rather
than imported — apps/api depends on the mcp-memory package for local dev convenience,
but these response shapes are part of the tool *contract*, not implementation, so a
small duplication keeps the two packages decoupled (see docs/DECISIONS.md).
"""

import uuid

from pydantic import BaseModel


class BeliefOut(BaseModel):
    id: uuid.UUID
    statement: str
    category: str
    confidence: float
    status: str


class EpisodeSummaryOut(BaseModel):
    id: uuid.UUID
    kind: str
    summary: str | None = None


class RecallResult(BaseModel):
    beliefs: list[BeliefOut] = []
    episodes: list[EpisodeSummaryOut] = []
    budget_tokens: int
    budget_used_tokens: int


class WriteEpisodeResult(BaseModel):
    episode_id: uuid.UUID
    anomalous: bool = False


class ReviseBeliefResult(BaseModel):
    belief_id: uuid.UUID
    status: str
    confidence: float


class ForgetResult(BaseModel):
    belief_id: uuid.UUID
    status: str
