"""The /chat agent runtime: a qwen-max tool loop over memory (via the MCP client),
the product catalog, and graduated reorder autonomy. Structured tool calls, bounded
iterations, and an honest "memory offline" reply if Qwen goes down mid-conversation
— never a 500 (CLAUDE.md architecture rule 4).
"""

import json
import logging

from app.core.config import get_settings
from app.models.autonomy import ACTION_REORDER, LEVEL_AUTO_NOTIFY
from app.models.episode import KIND_CHAT, KIND_SEARCH
from app.services import qwen, session_store
from app.services.autonomy import execute_auto_reorder, get_autonomy_status
from app.services.catalog import search_products
from app.services.embeddings import embed_cached
from app.services.memory_client import MemoryUnavailableError, memory_client

logger = logging.getLogger("memora.chat_agent")
settings = get_settings()

MAX_TOOL_ITERATIONS = 4

_SYSTEM_PROMPT = (
    "You are Memora, a shopping assistant with a transparent, editable memory of this "
    "shopper's preferences. Use the `recall` tool to check what you remember before "
    "answering questions about their preferences, and `catalog_search` to find products. "
    "If the shopper regularly repurchases something, use `create_reorder_proposal` — it "
    "tells you whether to ask for approval first or whether it already auto-reordered, so "
    "phrase your reply accordingly (never claim you reordered something unless the tool "
    "result says auto_reordered=true). Don't invent products or preferences you haven't "
    "looked up. Keep replies brief and conversational."
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": (
                "Recall this shopper's stored beliefs and recent activity relevant to a "
                "query, e.g. their style, budget, or size preferences."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to recall about, e.g. 'bag preferences'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "catalog_search",
            "description": "Search this store's product catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "what the shopper is looking for"},
                    "category": {"type": "string"},
                    "max_price": {"type": "number"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reorder_proposal",
            "description": (
                "Propose reordering a consumable product this shopper buys on a regular "
                "cadence. Returns whether it needs the shopper's approval or was already "
                "auto-reordered, based on their earned autonomy level."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "the product to reorder"}
                },
                "required": ["product_id"],
            },
        },
    },
]

_DEGRADED_REPLY = (
    "My memory's offline right now, so I can't pull up what I know about your "
    "preferences — try again in a moment."
)
_FALLBACK_REPLY = "Sorry, I'm having trouble putting together an answer right now."


def _summarize_anonymous_event(kind: str, payload: dict) -> str | None:
    """Best-effort, LLM-free summary of this session's own ephemeral event. No
    privacy concern surfacing it back to the same session's own recall call — it
    never leaves Redis or outlives the session either way (rule 5) — this just
    avoids spending a Qwen call annotating data that's about to expire anyway.
    """
    if kind == KIND_CHAT and "message" in payload:
        return f"asked: {payload['message']}"
    if kind == KIND_SEARCH and "query" in payload:
        return f"searched: {payload['query']}"
    if "product_id" in payload:
        return f"{kind} on product {payload['product_id']}"
    if "path" in payload:
        return f"{kind} at {payload['path']}"
    return None


async def _run_recall(
    store_id: str, shopper_id: str, session_id: str, query: str, persist: bool
) -> dict:
    if not persist:
        # Anonymous shopper: nothing's in Postgres to recall (rule 5) — the only
        # "memory" for this turn is this browsing session's own ephemeral events.
        events = await session_store.get_events(session_id)
        return {
            "beliefs": [],
            "recent_activity": [
                {
                    "kind": e["kind"],
                    "summary": _summarize_anonymous_event(e["kind"], e.get("payload", {})),
                }
                for e in events[-5:]
            ],
        }

    try:
        query_embedding = await embed_cached(query)
    except qwen.QwenUnavailableError:
        query_embedding = None

    result = await memory_client.recall(
        store_id=store_id, shopper_id=shopper_id, query=query, query_embedding=query_embedding
    )
    return {
        "beliefs": [
            {
                "statement": b.statement,
                "category": b.category,
                "confidence": b.confidence,
                "status": b.status,
            }
            for b in result.beliefs
        ],
        "recent_activity": [
            {"kind": e.kind, "summary": e.summary} for e in result.episodes
        ],
    }


async def _run_catalog_search(
    store_id: str, query: str, category: str | None, max_price: float | None
) -> dict:
    try:
        query_embedding = await embed_cached(query)
    except qwen.QwenUnavailableError:
        query_embedding = None

    products = await search_products(
        store_id, query_embedding=query_embedding, category=category, max_price=max_price
    )
    return {
        "products": [
            {
                "name": p.name,
                "category": p.category,
                "price": p.price,
                "currency": p.currency,
            }
            for p in products
        ]
    }


async def _run_create_reorder_proposal(
    store_id: str, shopper_id: str, persist: bool, product_id: str
) -> dict:
    if not persist:
        return {
            "error": (
                "reorder proposals need to remember this shopper across visits, and "
                "they're browsing anonymously right now"
            )
        }

    status = await get_autonomy_status(shopper_id, ACTION_REORDER)
    if status.level >= LEVEL_AUTO_NOTIFY:
        await execute_auto_reorder(store_id, shopper_id, product_id)
        return {"auto_reordered": True, "product_id": product_id}

    return {
        "auto_reordered": False,
        "needs_approval": True,
        "product_id": product_id,
        "level": status.level,
    }


async def _execute_tool_call(
    store_id: str, shopper_id: str, session_id: str, persist: bool, tool_call
) -> str:
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": f"invalid arguments for {name}"})

    if name == "recall":
        result = await _run_recall(
            store_id, shopper_id, session_id, args.get("query", ""), persist
        )
    elif name == "catalog_search":
        result = await _run_catalog_search(
            store_id, args.get("query", ""), args.get("category"), args.get("max_price")
        )
    elif name == "create_reorder_proposal":
        result = await _run_create_reorder_proposal(
            store_id, shopper_id, persist, args.get("product_id", "")
        )
    else:
        result = {"error": f"unknown tool {name}"}

    return json.dumps(result)


async def run_chat(
    store_id: str,
    shopper_id: str,
    session_id: str,
    message: str,
    history: list[dict] | None = None,
    persist: bool = True,
) -> tuple[str, bool]:
    """Returns (reply, degraded)."""
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})

    reply: str | None = None
    degraded = False

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response_message = await qwen.chat_message(
                messages, reasoning=True, tools=_TOOLS, tool_choice="auto"
            )
        except qwen.QwenUnavailableError as exc:
            logger.warning("qwen unavailable during chat: %s", exc)
            degraded = True
            break

        tool_calls = getattr(response_message, "tool_calls", None)
        if not tool_calls:
            reply = response_message.content or ""
            break

        messages.append(
            {
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
        )
        for tc in tool_calls:
            try:
                tool_result = await _execute_tool_call(
                    store_id, shopper_id, session_id, persist, tc
                )
            except MemoryUnavailableError as exc:
                logger.warning("memory unavailable during chat tool call: %s", exc)
                tool_result = json.dumps({"error": "memory unavailable"})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

    if degraded:
        return _DEGRADED_REPLY, True
    if reply is None:
        logger.warning(
            "chat tool loop exhausted %d iterations without a final reply", MAX_TOOL_ITERATIONS
        )
        return _FALLBACK_REPLY, False

    if not persist:
        await session_store.append_event(
            session_id, KIND_CHAT, {"message": message, "reply": reply}
        )
        return reply, False

    try:
        await memory_client.write_episode(
            store_id=store_id,
            shopper_id=shopper_id,
            session_id=session_id,
            kind=KIND_CHAT,
            payload={"message": message, "reply": reply},
            summary=message[:200],
            intent="unknown",
        )
    except MemoryUnavailableError as exc:
        logger.warning("failed to record chat episode: %s", exc)

    return reply, False
