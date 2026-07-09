"""Add notifications table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "type",
            sa.Enum("job_completed", "job_failed", name="notificationtype"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("shorts_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("video_id", sa.String(36), sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read"])


def downgrade():
    op.drop_index("ix_notifications_user_unread", "notifications")
    op.drop_index("ix_notifications_user_id", "notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notificationtype")
