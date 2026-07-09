"""Add clips_json to shorts

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('shorts', sa.Column('clips_json', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('shorts', 'clips_json')
