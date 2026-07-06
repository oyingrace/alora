from fastapi import APIRouter

from app.models.autonomy import ACTION_REORDER
from app.schemas.autonomy import AutonomyStatus, ReorderCandidate, ReorderDecisionIn, RevokeIn
from app.services.autonomy import (
    detect_reorder_candidates,
    get_autonomy_status,
    record_reorder_decision,
    revoke_autonomy,
)

router = APIRouter(tags=["autonomy"])


@router.get("/autonomy", response_model=AutonomyStatus)
async def autonomy_status(shopper_id: str, action_class: str = ACTION_REORDER) -> AutonomyStatus:
    return await get_autonomy_status(shopper_id, action_class)


@router.get("/autonomy/reorder/candidates", response_model=list[ReorderCandidate])
async def reorder_candidates(store_id: str, shopper_id: str) -> list[ReorderCandidate]:
    return await detect_reorder_candidates(store_id, shopper_id)


@router.post("/autonomy/reorder/decide", response_model=AutonomyStatus)
async def reorder_decide(payload: ReorderDecisionIn) -> AutonomyStatus:
    return await record_reorder_decision(
        payload.store_id, payload.shopper_id, payload.product_id, payload.approve
    )


@router.post("/autonomy/revoke", response_model=AutonomyStatus)
async def autonomy_revoke(payload: RevokeIn) -> AutonomyStatus:
    return await revoke_autonomy(payload.shopper_id, payload.action_class)
