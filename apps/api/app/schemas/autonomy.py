from datetime import datetime

from pydantic import BaseModel


class ReorderCandidate(BaseModel):
    product_id: str
    cadence_days: float
    last_purchased_at: datetime
    times_purchased: int


class AutonomyStatus(BaseModel):
    action_class: str
    level: int
    approvals: int
    rejections: int
    promoted: bool = False


class ReorderDecisionIn(BaseModel):
    store_id: str
    shopper_id: str
    product_id: str
    approve: bool


class RevokeIn(BaseModel):
    shopper_id: str
    action_class: str = "reorder"
