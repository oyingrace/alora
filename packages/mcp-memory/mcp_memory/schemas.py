import uuid

from pydantic import BaseModel, Field


class BeliefOut(BaseModel):
    id: uuid.UUID
    statement: str
    category: str
    confidence: float
    status: str


class EpisodeSummaryOut(BaseModel):
    id: uuid.UUID
    kind: str
    summary: str | None


class RecallResult(BaseModel):
    beliefs: list[BeliefOut] = Field(default_factory=list)
    episodes: list[EpisodeSummaryOut] = Field(default_factory=list)
    budget_tokens: int
    budget_used_tokens: int


class WriteEpisodeResult(BaseModel):
    episode_id: uuid.UUID


class ReviseBeliefResult(BaseModel):
    belief_id: uuid.UUID
    status: str
    confidence: float


class ForgetResult(BaseModel):
    belief_id: uuid.UUID
    status: str
