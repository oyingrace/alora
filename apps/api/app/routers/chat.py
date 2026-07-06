from fastapi import APIRouter

from app.schemas.chat import ChatIn, ChatOut
from app.services.chat_agent import run_chat

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn) -> ChatOut:
    reply, degraded = await run_chat(
        store_id=payload.store_id,
        shopper_id=payload.shopper_id,
        session_id=payload.session_id,
        message=payload.message,
        history=[m.model_dump() for m in payload.history],
        persist=payload.persist,
    )
    return ChatOut(reply=reply, degraded=degraded)
