"""add_remaining_fk_indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-11 12:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    def index_exists(table_name, index_name):
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            return index_name in existing_indexes
        except Exception:
            return False

    # TeamMembership: add indexes on user_id and team_id
    if not index_exists('team_memberships', 'ix_team_memberships_user_id'):
        with op.batch_alter_table('team_memberships', schema=None) as batch_op:
            batch_op.create_index(
                'ix_team_memberships_user_id',
                ['user_id'],
                unique=False,
            )

    if not index_exists('team_memberships', 'ix_team_memberships_team_id'):
        with op.batch_alter_table('team_memberships', schema=None) as batch_op:
            batch_op.create_index(
                'ix_team_memberships_team_id',
                ['team_id'],
                unique=False,
            )

    # Exposure: add index on requested_by_principal_id
    if not index_exists('exposures', 'ix_exposures_requested_by_principal_id'):
        with op.batch_alter_table('exposures', schema=None) as batch_op:
            batch_op.create_index(
                'ix_exposures_requested_by_principal_id',
                ['requested_by_principal_id'],
                unique=False,
            )

    # AccessGrant: add index on created_by_principal_id
    if not index_exists('access_grants', 'ix_access_grants_created_by_principal_id'):
        with op.batch_alter_table('access_grants', schema=None) as batch_op:
            batch_op.create_index(
                'ix_access_grants_created_by_principal_id',
                ['created_by_principal_id'],
                unique=False,
            )


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    def index_exists(table_name, index_name):
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            return index_name in existing_indexes
        except Exception:
            return False

    if index_exists('access_grants', 'ix_access_grants_created_by_principal_id'):
        with op.batch_alter_table('access_grants', schema=None) as batch_op:
            batch_op.drop_index('ix_access_grants_created_by_principal_id')

    if index_exists('exposures', 'ix_exposures_requested_by_principal_id'):
        with op.batch_alter_table('exposures', schema=None) as batch_op:
            batch_op.drop_index('ix_exposures_requested_by_principal_id')

    if index_exists('team_memberships', 'ix_team_memberships_team_id'):
        with op.batch_alter_table('team_memberships', schema=None) as batch_op:
            batch_op.drop_index('ix_team_memberships_team_id')

    if index_exists('team_memberships', 'ix_team_memberships_user_id'):
        with op.batch_alter_table('team_memberships', schema=None) as batch_op:
            batch_op.drop_index('ix_team_memberships_user_id')
