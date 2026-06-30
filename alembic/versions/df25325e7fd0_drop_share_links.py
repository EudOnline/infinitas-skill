"""drop_share_links

Revision ID: df25325e7fd0
Revises: e5f6a7b8c9d0
Create Date: 2026-06-13 04:16:28.430913
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'df25325e7fd0'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_share_links_release_id'), table_name='share_links')
    op.drop_index(op.f('ix_share_links_slug'), table_name='share_links')
    op.drop_table('share_links')


def downgrade() -> None:
    # Re-creating the table is provided only for rollback safety; data is lost.
    op.create_table(
        'share_links',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('release_id', sa.Integer, nullable=False),
        sa.Column('name', sa.String(200), nullable=False, server_default=''),
        sa.Column('slug', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False, server_default=''),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_uses', sa.Integer, nullable=True),
        sa.Column('used_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_principal_id', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.ForeignKeyConstraint(['created_by_principal_id'], ['principals.id']),
    )
    op.create_index(op.f('ix_share_links_release_id'), 'share_links', ['release_id'], unique=False)
    op.create_index(op.f('ix_share_links_slug'), 'share_links', ['slug'], unique=True)
