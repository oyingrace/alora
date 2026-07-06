"""Episode summarization + intent classification via qwen-turbo.

Validated against a strict Pydantic contract; on a bad response, retries once with
the validation error appended to the conversation, then falls back to a neutral
annotation rather than ever raising — CLAUDE.md architecture rules 3 and 4 (structured
outputs validated, retry once, graceful degrade, never 500).
"""

import json
import logging
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.services import qwen

logger = logging.getLogger("memora.intent")

Intent = Literal["self", "gift", "research", "unknown"]


class EpisodeAnnotation(BaseModel):
    summary: str
    intent: Intent


_SYSTEM_PROMPT = (
    "You annotate a single shopper behavioral event for an e-commerce memory system. "
    "Given the event kind and payload, respond with strict JSON only, matching exactly "
    'this shape: {"summary": "<one-line summary, under 15 words>", '
    '"intent": "self|gift|research|unknown"}. Use "unknown" whenever intent isn\'t '
    "clearly indicated by the event alone — do not guess."
)


async def annotate_episode(kind: str, payload: dict) -> EpisodeAnnotation:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps({"kind": kind, "payload": payload})},
    ]
    raw = ""

    for attempt in range(2):
        try:
            raw = await qwen.chat(messages, reasoning=False)
            return EpisodeAnnotation.model_validate_json(raw)
        except qwen.QwenUnavailableError as exc:
            logger.warning("qwen unavailable during annotation, falling back: %s", exc)
            break
        except (ValidationError, ValueError) as exc:
            logger.warning("annotation validation failed (attempt %d): %s", attempt + 1, exc)
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"That response was invalid: {exc}. Return corrected strict JSON only.",
                }
            )

    return EpisodeAnnotation(summary=f"{kind} event", intent="unknown")
