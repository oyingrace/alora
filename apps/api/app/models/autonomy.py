from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# autonomy.action_class values
ACTION_REORDER = "reorder"
ACTION_PRICE_WATCH = "price_watch"
ACTION_CART_BUILD = "cart_build"

# autonomy.level values
LEVEL_RECOMMEND_ONLY = 0
LEVEL_ASK_FIRST = 1
LEVEL_AUTO_NOTIFY = 2

PROMOTION_APPROVALS_REQUIRED = 3


class Autonomy(Base):
    """Graduated autonomy per shopper per action class."""

    __tablename__ = "autonomy"

    shopper_id: Mapped[str] = mapped_column(String, primary_key=True)
    action_class: Mapped[str] = mapped_column(String, primary_key=True)

    level: Mapped[int] = mapped_column(Integer, default=LEVEL_RECOMMEND_ONLY)
    track_record: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
