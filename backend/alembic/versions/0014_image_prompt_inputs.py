"""image: add prompt + input_paths (text_to_image, image_to_shorts)

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("input_paths", sa.Text(), nullable=True))
    op.add_column("images", sa.Column("prompt", sa.Text(), nullable=True))
    op.add_column("images", sa.Column("aspect_ratio", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("images", "aspect_ratio")
    op.drop_column("images", "prompt")
    op.drop_column("images", "input_paths")
