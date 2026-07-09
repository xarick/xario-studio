"""add transcript_segments to videos (transcribe / STT mode)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("transcript_segments", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "transcript_segments")
