"""initial schema: episodes, beliefs, autonomy, memory_audit

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", sa.String, nullable=False),
        sa.Column("shopper_id", sa.String, nullable=False),
        sa.Column("session_id", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("summary", sa.String, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("intent", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_episodes_store_id", "episodes", ["store_id"])
    op.create_index("ix_episodes_shopper_id", "episodes", ["shopper_id"])
    op.create_index("ix_episodes_session_id", "episodes", ["session_id"])
    op.create_index("ix_episodes_kind", "episodes", ["kind"])

    op.create_table(
        "beliefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", sa.String, nullable=False),
        sa.Column("shopper_id", sa.String, nullable=False),
        sa.Column("statement", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "evidence", sa.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False
        ),
        sa.Column("status", sa.String, nullable=False),
        sa.Column(
            "last_reinforced_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("decay_half_life_days", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_beliefs_store_id", "beliefs", ["store_id"])
    op.create_index("ix_beliefs_shopper_id", "beliefs", ["shopper_id"])
    op.create_index("ix_beliefs_category", "beliefs", ["category"])
    op.create_index("ix_beliefs_status", "beliefs", ["status"])

    op.create_table(
        "autonomy",
        sa.Column("shopper_id", sa.String, primary_key=True),
        sa.Column("action_class", sa.String, primary_key=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("track_record", sa.JSON, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "memory_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("belief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", sa.String, nullable=False),
        sa.Column("shopper_id", sa.String, nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_audit_belief_id", "memory_audit", ["belief_id"])
    op.create_index("ix_memory_audit_store_id", "memory_audit", ["store_id"])
    op.create_index("ix_memory_audit_shopper_id", "memory_audit", ["shopper_id"])


def downgrade() -> None:
    op.drop_table("memory_audit")
    op.drop_table("autonomy")
    op.drop_table("beliefs")
    op.drop_table("episodes")
