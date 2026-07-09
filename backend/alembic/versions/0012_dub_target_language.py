"""add dub_target_language to videos (translate + dub mode)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("dub_target_language", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "dub_target_language")
