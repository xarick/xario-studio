"""add tts_voice to videos (text-to-speech mode)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("tts_voice", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "tts_voice")
