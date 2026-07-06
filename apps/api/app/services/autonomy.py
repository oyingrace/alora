"""Graduated autonomy for the reorder action class (BUILD_PLAN.md §5.2/§4 Phase 4):
detect a consumable repurchase cadence from purchase episodes, propose a reorder,
track approvals, and promote from ask-first to auto+notify after enough of them.

Reads purchase episodes directly (a batch cadence-detection sweep across a
shopper's whole purchase history, not a single-query `recall`) for the same reason
consolidation/decay do; the `autonomy` table itself is a normal apps/api table like
the product catalog — it's an operational trust-level tracker, not shopper
"belief" memory, so it isn't behind the MCP tools either. The reorder *episode*
itself, though, is real episodic memory and goes through `write_episode`.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app import db
from app.models import Autonomy, Episode
from app.models.autonomy import (
    ACTION_REORDER,
    LEVEL_ASK_FIRST,
    LEVEL_AUTO_NOTIFY,
    LEVEL_RECOMMEND_ONLY,
    PROMOTION_APPROVALS_REQUIRED,
)
from app.models.episode import KIND_PURCHASE, KIND_REORDER
from app.schemas.autonomy import AutonomyStatus, ReorderCandidate
from app.services.memory_client import MemoryUnavailableError, memory_client

logger = logging.getLogger("memora.autonomy")

MIN_PURCHASES_FOR_CADENCE = 2


async def detect_reorder_candidates(store_id: str, shopper_id: str) -> list[ReorderCandidate]:
    """A product is a reorder candidate once it's been bought at least twice and
    the average interval between purchases has elapsed since the last one.
    """
    async with db.async_session() as session:
        rows = (
            await session.execute(
                select(Episode)
                .where(
                    Episode.store_id == store_id,
                    Episode.shopper_id == shopper_id,
                    Episode.kind.in_([KIND_PURCHASE, KIND_REORDER]),
                )
                .order_by(Episode.created_at)
            )
        ).scalars()
        purchases = [
            (e.payload.get("product_id"), e.created_at) for e in rows if e.payload.get("product_id")
        ]

    by_product: dict[str, list[datetime]] = {}
    for product_id, created_at in purchases:
        by_product.setdefault(product_id, []).append(created_at)

    now = datetime.now(UTC)
    candidates: list[ReorderCandidate] = []
    for product_id, dates in by_product.items():
        if len(dates) < MIN_PURCHASES_FOR_CADENCE:
            continue
        dates.sort()
        intervals = [
            (dates[i + 1] - dates[i]).total_seconds() / 86400 for i in range(len(dates) - 1)
        ]
        avg_interval = sum(intervals) / len(intervals)
        last_purchase = dates[-1]
        days_since_last = (now - last_purchase).total_seconds() / 86400
        if days_since_last >= avg_interval:
            candidates.append(
                ReorderCandidate(
                    product_id=product_id,
                    cadence_days=round(avg_interval, 1),
                    last_purchased_at=last_purchase,
                    times_purchased=len(dates),
                )
            )
    return candidates


def _status_from_row(
    row: Autonomy | None, action_class: str, *, promoted: bool = False
) -> AutonomyStatus:
    if row is None:
        # No history yet defaults to ask-first: detecting a candidate at all
        # already implies "propose and wait for approval" behavior.
        return AutonomyStatus(
            action_class=action_class, level=LEVEL_ASK_FIRST, approvals=0, rejections=0
        )
    track = row.track_record or {}
    return AutonomyStatus(
        action_class=action_class,
        level=row.level,
        approvals=track.get("approvals", 0),
        rejections=track.get("rejections", 0),
        promoted=promoted,
    )


async def get_autonomy_status(
    shopper_id: str, action_class: str = ACTION_REORDER
) -> AutonomyStatus:
    async with db.async_session() as session:
        row = await session.get(Autonomy, (shopper_id, action_class))
        return _status_from_row(row, action_class)


async def record_reorder_decision(
    store_id: str, shopper_id: str, product_id: str, approve: bool
) -> AutonomyStatus:
    """Records a shopper's approve/reject of a proposed reorder. Promotes to
    auto+notify after PROMOTION_APPROVALS_REQUIRED approvals.
    """
    promoted = False
    async with db.async_session() as session:
        row = await session.get(Autonomy, (shopper_id, ACTION_REORDER))
        if row is None:
            row = Autonomy(
                shopper_id=shopper_id,
                action_class=ACTION_REORDER,
                level=LEVEL_ASK_FIRST,
                track_record={},
            )
            session.add(row)

        track = dict(row.track_record or {})
        if approve:
            track["approvals"] = track.get("approvals", 0) + 1
            if row.level < LEVEL_AUTO_NOTIFY and track["approvals"] >= PROMOTION_APPROVALS_REQUIRED:
                row.level = LEVEL_AUTO_NOTIFY
                promoted = True
            elif row.level == LEVEL_RECOMMEND_ONLY:
                # a decision after a revoke means the shopper opted back in
                row.level = LEVEL_ASK_FIRST
        else:
            track["rejections"] = track.get("rejections", 0) + 1
        row.track_record = track

        await session.commit()
        status = _status_from_row(row, ACTION_REORDER, promoted=promoted)

    if approve:
        try:
            await memory_client.write_episode(
                store_id=store_id,
                shopper_id=shopper_id,
                session_id="autonomy",
                kind=KIND_REORDER,
                payload={"product_id": product_id, "auto": False},
                summary=f"Reordered {product_id}",
                intent="self",
            )
        except MemoryUnavailableError as exc:
            logger.warning("failed to record reorder episode: %s", exc)

    return status


async def execute_auto_reorder(store_id: str, shopper_id: str, product_id: str) -> None:
    """Level 2 (auto+notify): reorder without asking, and log it as an episode."""
    try:
        await memory_client.write_episode(
            store_id=store_id,
            shopper_id=shopper_id,
            session_id="autonomy",
            kind=KIND_REORDER,
            payload={"product_id": product_id, "auto": True},
            summary=f"Auto-reordered {product_id}",
            intent="self",
        )
    except MemoryUnavailableError as exc:
        logger.warning("failed to record auto-reorder episode: %s", exc)


async def revoke_autonomy(shopper_id: str, action_class: str = ACTION_REORDER) -> AutonomyStatus:
    """One-click revoke: back to level 0 (recommend-only, no formal proposals)."""
    async with db.async_session() as session:
        row = await session.get(Autonomy, (shopper_id, action_class))
        if row is None:
            return AutonomyStatus(
                action_class=action_class,
                level=LEVEL_RECOMMEND_ONLY,
                approvals=0,
                rejections=0,
            )

        row.level = LEVEL_RECOMMEND_ONLY
        await session.commit()
        return _status_from_row(row, action_class)
