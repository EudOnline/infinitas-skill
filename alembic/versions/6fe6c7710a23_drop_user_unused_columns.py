"""drop_user_unused_columns

Revision ID: 6fe6c7710a23
Revises: df25325e7fd0
Create Date: 2026-06-15 14:33:36.436989
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6fe6c7710a23'
down_revision = 'df25325e7fd0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_users_token'), table_name='users')
    op.drop_column('users', 'token')
    op.drop_column('users', 'dark_bg_id')
    op.drop_column('users', 'light_bg_id')


def downgrade() -> None:
    op.add_column('users', sa.Column('light_bg_id', sa.VARCHAR(length=64), nullable=True))
    op.add_column('users', sa.Column('dark_bg_id', sa.VARCHAR(length=64), nullable=True))
    op.add_column('users', sa.Column('token', sa.VARCHAR(length=255), nullable=True))
    op.create_index(op.f('ix_users_token'), 'users', ['token'], unique=True)
