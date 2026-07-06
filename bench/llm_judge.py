"""qwen-max-as-judge: scores how well a set of recommendations matches a persona's
stated "ideal" preference at a given point in its scripted story (BUILD_PLAN.md §7,
"rec relevance (LLM-judged)"). Goes through app.services.qwen like everything else —
no separate client, no separate token accounting.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from app.services import qwen

logger = logging.getLogger("bench.llm_judge")

_JUDGE_SYSTEM_PROMPT = (
    "You are grading an e-commerce recommendation list for relevance. Given a "
    "description of what this shopper actually wants right now and the list of "
    "products they were recommended, score how well the list matches, from 0 (no "
    "recommendations fit) to 1 (every recommendation fits well). Respond with strict "
    'JSON only: {"score": <0..1>}.'
)


class _JudgeResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)


async def judge_relevance(ideal_description: str, recs: list[dict]) -> float:
    """Returns 0.0 if there's nothing to judge or Qwen is unavailable — a benchmark
    run should never crash on a single bad judge call, it should just record a zero.
    """
    if not recs:
        return 0.0

    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"ideal_description": ideal_description, "recs": recs}),
        },
    ]
    try:
        raw = await qwen.chat(messages, reasoning=False)
        return _JudgeResponse.model_validate_json(raw).score
    except (qwen.QwenUnavailableError, ValidationError, ValueError) as exc:
        logger.warning("judge call failed, scoring 0.0: %s", exc)
        return 0.0
