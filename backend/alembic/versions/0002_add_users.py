"""add users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("superadmin", "admin", "user", name="userrole"),
            nullable=False,
            server_default="user",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.add_column("videos", sa.Column(
        "user_id", sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ))
    op.create_index("ix_videos_user_id", "videos", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_videos_user_id", "videos")
    op.drop_column("videos", "user_id")
    op.drop_index("ix_users_username", "users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
