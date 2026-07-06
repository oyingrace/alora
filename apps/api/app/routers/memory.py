import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import db
from app.models import Belief, MemoryAudit
from app.schemas.inspector import AuditEntry, InspectorBelief, MemoryListOut, ReviseBeliefIn
from app.schemas.memory import ForgetResult, ReviseBeliefResult
from app.services.memory_client import MemoryToolError, MemoryUnavailableError, memory_client

router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=MemoryListOut)
async def list_memory(store_id: str, shopper_id: str) -> MemoryListOut:
    """Everything the Memory Inspector shows: every belief (active/decaying/deprecated
    alike, so the shopper can see what's fading) plus the full audit trail — this is a
    "show me everything" read, unlike `recall`'s budget-capped, active-only shape, so
    it's a direct DB read rather than a forced fit through that tool.
    """
    async with db.async_session() as session:
        beliefs = (
            (
                await session.execute(
                    select(Belief)
                    .where(Belief.store_id == store_id, Belief.shopper_id == shopper_id)
                    .order_by(Belief.confidence.desc())
                )
            )
            .scalars()
            .all()
        )

        belief_ids = [b.id for b in beliefs]
        audit_rows = []
        if belief_ids:
            audit_rows = (
                (
                    await session.execute(
                        select(MemoryAudit)
                        .where(MemoryAudit.belief_id.in_(belief_ids))
                        .order_by(MemoryAudit.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )

    return MemoryListOut(
        beliefs=[
            InspectorBelief(
                id=b.id,
                statement=b.statement,
                category=b.category,
                confidence=b.confidence,
                status=b.status,
                last_reinforced_at=b.last_reinforced_at,
            )
            for b in beliefs
        ],
        audit=[
            AuditEntry(
                id=a.id, belief_id=a.belief_id, action=a.action, reason=a.reason,
                created_at=a.created_at,
            )
            for a in audit_rows
        ],
    )


@router.patch("/memory/{belief_id}", response_model=ReviseBeliefResult)
async def correct_belief(belief_id: uuid.UUID, payload: ReviseBeliefIn) -> ReviseBeliefResult:
    """Shopper-initiated correction in the Inspector — always audited as "revise"."""
    try:
        return await memory_client.revise_belief(
            action="revise",
            belief_id=belief_id,
            reason=payload.reason,
            statement=payload.statement,
            confidence=payload.confidence,
        )
    except MemoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail="memory layer unavailable") from exc
    except MemoryToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/memory/{belief_id}", response_model=ForgetResult)
async def delete_belief(belief_id: uuid.UUID, reason: str) -> ForgetResult:
    """Shopper deletes a belief in the Inspector — audited distinctly as "user_delete"
    (vs. "deprecate" for system-driven single-shot deprecation).
    """
    try:
        return await memory_client.forget(belief_id, reason=reason, action="user_delete")
    except MemoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail="memory layer unavailable") from exc
    except MemoryToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
