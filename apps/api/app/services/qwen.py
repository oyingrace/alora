"""Single choke point for all Qwen Cloud API calls.

Every LLM/embedding call in this codebase goes through this module — this is the file
that proves Alibaba Cloud / Qwen Cloud API usage to hackathon judges. Do not call the
`openai` SDK directly from anywhere else in the app.

Model IDs are never hardcoded here or elsewhere; they come from `Settings`
(`MODEL_REASONING`, `MODEL_FAST`, `MODEL_VISION`, `MODEL_EMBED`).
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger("memora.qwen")

_RETRYABLE = (APIConnectionError, APITimeoutError, APIStatusError)
_DEFAULT_TIMEOUT_S = 20.0


class QwenUnavailableError(RuntimeError):
    """Raised after retries are exhausted. Callers must degrade gracefully, never 500."""


@lru_cache
def _client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_base_url,
        timeout=_DEFAULT_TIMEOUT_S,
    )


def _log_usage(call: str, model: str, usage: Any, elapsed_s: float) -> None:
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    logger.info(
        "qwen call=%s model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
        "elapsed_ms=%d",
        call,
        model,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        int(elapsed_s * 1000),
    )


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _chat(*, model: str, messages: list[dict], **kwargs: Any):
    return await _client().chat.completions.create(model=model, messages=messages, **kwargs)


async def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    reasoning: bool = False,
    **kwargs: Any,
) -> str:
    """Chat completion. Defaults to MODEL_FAST; pass reasoning=True for MODEL_REASONING.

    Budget discipline (see CLAUDE.md): MODEL_REASONING is reserved for /chat and the
    consolidation worker — everything else should use the fast model.
    """
    settings = get_settings()
    resolved_model = model or (settings.model_reasoning if reasoning else settings.model_fast)

    start = time.monotonic()
    try:
        response = await _chat(model=resolved_model, messages=messages, **kwargs)
    except _RETRYABLE as exc:
        logger.error("qwen chat failed after retries: model=%s error=%s", resolved_model, exc)
        raise QwenUnavailableError(str(exc)) from exc

    _log_usage("chat", resolved_model, response.usage, time.monotonic() - start)
    return response.choices[0].message.content or ""


async def chat_message(
    messages: list[dict],
    *,
    model: str | None = None,
    reasoning: bool = False,
    **kwargs: Any,
):
    """Like `chat()` but returns the raw response message (content + tool_calls)
    instead of just the text — for callers driving a tool-calling loop (/chat).
    """
    settings = get_settings()
    resolved_model = model or (settings.model_reasoning if reasoning else settings.model_fast)

    start = time.monotonic()
    try:
        response = await _chat(model=resolved_model, messages=messages, **kwargs)
    except _RETRYABLE as exc:
        logger.error("qwen chat failed after retries: model=%s error=%s", resolved_model, exc)
        raise QwenUnavailableError(str(exc)) from exc

    _log_usage("chat_message", resolved_model, response.usage, time.monotonic() - start)
    return response.choices[0].message


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _embed(*, model: str, texts: list[str]):
    return await _client().embeddings.create(model=model, input=texts)


async def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Embed a batch of texts with MODEL_EMBED. Callers should cache by content hash."""
    settings = get_settings()
    resolved_model = model or settings.model_embed

    start = time.monotonic()
    try:
        response = await _embed(model=resolved_model, texts=texts)
    except _RETRYABLE as exc:
        logger.error("qwen embed failed after retries: model=%s error=%s", resolved_model, exc)
        raise QwenUnavailableError(str(exc)) from exc

    _log_usage("embed", resolved_model, response.usage, time.monotonic() - start)
    return [item.embedding for item in response.data]


async def vision_tag(image_url: str, prompt: str) -> str:
    """Tag a product image with MODEL_VISION (e.g. style/material/color attributes).

    Callers should cache results by image content hash — VL calls are the most
    expensive line item in the token budget.
    """
    settings = get_settings()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    start = time.monotonic()
    try:
        response = await _chat(model=settings.model_vision, messages=messages)
    except _RETRYABLE as exc:
        logger.error("qwen vision_tag failed after retries: error=%s", exc)
        raise QwenUnavailableError(str(exc)) from exc

    _log_usage("vision_tag", settings.model_vision, response.usage, time.monotonic() - start)
    return response.choices[0].message.content or ""
