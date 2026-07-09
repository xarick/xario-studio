"""add generation_mode to videos

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column(
            "generation_mode",
            sa.String(length=16),
            nullable=False,
            server_default="smart",
        ),
    )


def downgrade() -> None:
    op.drop_column("videos", "generation_mode")
