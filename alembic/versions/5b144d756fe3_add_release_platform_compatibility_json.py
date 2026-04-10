"""add release platform_compatibility_json

Revision ID: 5b144d756fe3
Revises: 20260405_0006
Create Date: 2026-04-08 22:52:45.132427
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b144d756fe3'
down_revision = '20260405_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('releases', sa.Column('platform_compatibility_json', sa.Text(), nullable=False, server_default='{}'))


def downgrade() -> None:
    op.drop_column('releases', 'platform_compatibility_json')
