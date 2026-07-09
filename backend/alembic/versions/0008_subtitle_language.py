"""add subtitle_language to videos

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("subtitle_language", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "subtitle_language")
