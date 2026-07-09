"""initial

Revision ID: 0001
Revises:
Create Date: 2026-06-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.Enum("upload", "url", name="videosourcetype"), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("shorts_requested", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "downloading", "processing", "completed", "failed", name="videostatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("progress_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "shorts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("video_id", sa.String(36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("index_number", sa.Integer, nullable=False),
        sa.Column("start_time", sa.Float, nullable=False),
        sa.Column("end_time", sa.Float, nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="shortstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index("ix_shorts_video_id", "shorts", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_shorts_video_id", "shorts")
    op.drop_table("shorts")
    op.drop_table("videos")
    op.execute("DROP TYPE IF EXISTS shortstatus")
    op.execute("DROP TYPE IF EXISTS videostatus")
    op.execute("DROP TYPE IF EXISTS videosourcetype")
