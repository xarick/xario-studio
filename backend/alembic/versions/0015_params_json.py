"""add params_json to videos (edit/tool modes)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("params_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "params_json")
