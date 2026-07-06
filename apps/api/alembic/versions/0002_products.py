"""products catalog table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", sa.String, nullable=False),
        sa.Column("external_id", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("currency", sa.String, nullable=False),
        sa.Column("image_url", sa.String, nullable=True),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_products_store_id", "products", ["store_id"])
    op.create_index("ix_products_external_id", "products", ["external_id"])
    op.create_index("ix_products_category", "products", ["category"])


def downgrade() -> None:
    op.drop_table("products")
