"""create images table (image processing: background removal, …)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("output_path", sa.String(1024), nullable=True),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_images_user_id", "images", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_images_user_id", table_name="images")
    op.drop_table("images")
