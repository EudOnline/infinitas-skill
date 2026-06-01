"""add_rate_limit_entries_table

Revision ID: cddf6871f17d
Revises: d7e124c31af2
Create Date: 2026-06-01 14:38:58.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'cddf6871f17d'
down_revision = 'd7e124c31af2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rate_limit_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('rate_limit_entries', schema=None) as batch_op:
        batch_op.create_index('ix_rate_limit_entries_key', ['key'], unique=False)
        batch_op.create_index('ix_rate_limit_entries_window_start', ['window_start'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('rate_limit_entries', schema=None) as batch_op:
        batch_op.drop_index('ix_rate_limit_entries_window_start')
        batch_op.drop_index('ix_rate_limit_entries_key')
    op.drop_table('rate_limit_entries')
