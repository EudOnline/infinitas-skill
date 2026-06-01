"""add user password hash

Revision ID: 52ab6f2e589e
Revises: 20260424_0001
Create Date: 2026-06-01 12:40:13.990964
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '52ab6f2e589e'
down_revision = '20260424_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_hash')
