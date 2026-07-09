"""seed super admin user from env

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.core.config import settings
    from app.core.security import hash_password

    op.execute(
        sa.text("""
            INSERT INTO users (id, username, hashed_password, role, is_active, created_at, updated_at)
            VALUES (:id, :username, :pwd, 'superadmin', true, NOW(), NOW())
            ON CONFLICT (username) DO UPDATE
                SET role = 'superadmin',
                    hashed_password = EXCLUDED.hashed_password,
                    is_active = true
        """).bindparams(
            id=str(uuid.uuid4()),
            username=settings.SUPER_ADMIN_USERNAME,
            pwd=hash_password(settings.SUPER_ADMIN_PASSWORD),
        )
    )


def downgrade() -> None:
    from app.core.config import settings

    op.execute(
        sa.text("DELETE FROM users WHERE username = :username").bindparams(
            username=settings.SUPER_ADMIN_USERNAME
        )
    )
