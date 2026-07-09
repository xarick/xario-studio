"""add transcript_text to videos (subtitle align mode)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("transcript_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "transcript_text")
