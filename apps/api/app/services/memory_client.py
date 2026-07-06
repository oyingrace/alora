"""The only path apps/api uses to touch memory (episodes/beliefs) — everything goes
through the MCP tools in packages/mcp-memory over stdio, never direct SQL (CLAUDE.md
architecture rule 1). One persistent subprocess + session for the app's lifetime,
wired up in app.main's lifespan.
"""

import logging
import sys
import uuid
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.schemas.memory import (
    BeliefOut,
    EpisodeSummaryOut,
    ForgetResult,
    RecallResult,
    ReviseBeliefResult,
    WriteEpisodeResult,
)

logger = logging.getLogger("memora.memory_client")


class MemoryUnavailableError(RuntimeError):
    """Raised when the MCP memory server can't be reached or returns an error.

    Callers must degrade gracefully (rule 4): /recs falls back to cached/similarity
    results, /chat returns an honest "memory offline" message — never a 500.
    """


class MemoryClient:
    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        self._stack = AsyncExitStack()
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_memory.server"])
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        logger.info("connected to mcp-memory server")

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise MemoryUnavailableError("memory client is not connected")
        return self._session

    async def _call(self, tool: str, arguments: dict) -> dict:
        session = self._require_session()
        try:
            result = await session.call_tool(tool, arguments)
        except Exception as exc:  # noqa: BLE001 - any transport failure degrades gracefully
            logger.error("mcp tool call failed: tool=%s error=%s", tool, exc)
            raise MemoryUnavailableError(str(exc)) from exc

        if result.isError:
            message = result.content[0].text if result.content else "unknown error"
            logger.error("mcp tool returned error: tool=%s message=%s", tool, message)
            raise MemoryUnavailableError(message)

        if result.structuredContent is not None:
            return result.structuredContent
        raise MemoryUnavailableError(f"tool {tool} returned no structured content")

    async def recall(
        self,
        store_id: str,
        shopper_id: str,
        query: str,
        budget_tokens: int | None = None,
        query_embedding: list[float] | None = None,
    ) -> RecallResult:
        data = await self._call(
            "recall",
            {
                "store_id": store_id,
                "shopper_id": shopper_id,
                "query": query,
                "budget_tokens": budget_tokens,
                "query_embedding": query_embedding,
            },
        )
        return RecallResult(
            beliefs=[BeliefOut(**b) for b in data.get("beliefs", [])],
            episodes=[EpisodeSummaryOut(**e) for e in data.get("episodes", [])],
            budget_tokens=data["budget_tokens"],
            budget_used_tokens=data["budget_used_tokens"],
        )

    async def write_episode(
        self,
        store_id: str,
        shopper_id: str,
        session_id: str,
        kind: str,
        payload: dict,
        summary: str | None = None,
        intent: str = "unknown",
        embedding: list[float] | None = None,
    ) -> WriteEpisodeResult:
        data = await self._call(
            "write_episode",
            {
                "store_id": store_id,
                "shopper_id": shopper_id,
                "session_id": session_id,
                "kind": kind,
                "payload": payload,
                "summary": summary,
                "intent": intent,
                "embedding": embedding,
            },
        )
        return WriteEpisodeResult(**data)

    async def revise_belief(
        self,
        action: str,
        reason: str,
        belief_id: uuid.UUID | None = None,
        store_id: str | None = None,
        shopper_id: str | None = None,
        statement: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
        evidence_episode_ids: list[uuid.UUID] | None = None,
    ) -> ReviseBeliefResult:
        """`action` must be one of "create" (belief_id=None) / "reinforce" / "revise" /
        "decay" (belief_id set) — caller-supplied so a decay-driven confidence drop is
        never misread as reinforcement in the memory_audit trail.
        """
        data = await self._call(
            "revise_belief",
            {
                "action": action,
                "reason": reason,
                "belief_id": str(belief_id) if belief_id else None,
                "store_id": store_id,
                "shopper_id": shopper_id,
                "statement": statement,
                "category": category,
                "confidence": confidence,
                "evidence_episode_ids": [str(i) for i in (evidence_episode_ids or [])],
            },
        )
        return ReviseBeliefResult(**data)

    async def forget(
        self, belief_id: uuid.UUID, reason: str, action: str = "deprecate"
    ) -> ForgetResult:
        """`action="user_delete"` when the shopper deletes it in the Inspector;
        "deprecate" (default) for system-driven single-shot deprecation.
        """
        data = await self._call(
            "forget", {"belief_id": str(belief_id), "reason": reason, "action": action}
        )
        return ForgetResult(**data)


memory_client = MemoryClient()
