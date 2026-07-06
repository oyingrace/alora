"""The JSON contract the consolidation LLM call (qwen-max, in apps/api) must return.

Kept dependency-free (pure Pydantic, no DB/IO) so it's shared as-is by apps/api's
consolidation worker without pulling in apps/api's dependencies — see
docs/DECISIONS.md for why this one module is the exception to "mcp-memory never
depends on apps/api" (the reverse direction, apps/api depending on this module, is
fine and avoids duplicating the contract in two places).
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

MutationAction = Literal["create", "reinforce", "revise", "deprecate"]


class BeliefMutation(BaseModel):
    action: MutationAction
    belief_id: uuid.UUID | None = None
    statement: str | None = None
    category: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_episode_ids: list[uuid.UUID] = Field(default_factory=list)
    reason: str

    def model_post_init(self, __context: object) -> None:
        if self.action == "create" and (
            self.statement is None or self.category is None or self.confidence is None
        ):
            raise ValueError("create mutations require statement, category, and confidence")
        if self.action in ("revise", "reinforce", "deprecate") and self.belief_id is None:
            raise ValueError(f"{self.action} mutations require belief_id")


class ConsolidationResponse(BaseModel):
    mutations: list[BeliefMutation] = Field(default_factory=list)


def parse_consolidation_response(raw_json: str) -> ConsolidationResponse:
    """Raises pydantic.ValidationError / pydantic_core.ValidationError on bad input —
    callers retry once with the error appended, then fall back gracefully (never 500),
    per CLAUDE.md architecture rule 3.
    """
    return ConsolidationResponse.model_validate_json(raw_json)


__all__ = ["BeliefMutation", "ConsolidationResponse", "parse_consolidation_response", "ValidationError"]
