"""add_performance_indexes

Revision ID: c8f3e21d4a8b
Revises: 2a5e8f3c7d9e
Create Date: 2026-06-04 14:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = 'c8f3e21d4a8b'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get bind to check existing indexes
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    # Helper to check if index exists
    def index_exists(table_name, index_name):
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            return index_name in existing_indexes
        except Exception:
            return False

    # Add index for audit events if it doesn't exist
    if not index_exists('audit_events', 'ix_audit_events_occurred_at'):
        with op.batch_alter_table('audit_events', schema=None) as batch_op:
            batch_op.create_index(
                'ix_audit_events_occurred_at',
                ['occurred_at'],
                unique=False,
            )

    # Add index for releases.skill_version_id if it doesn't exist
    if not index_exists('releases', 'ix_releases_skill_version_id'):
        with op.batch_alter_table('releases', schema=None) as batch_op:
            batch_op.create_index(
                'ix_releases_skill_version_id',
                ['skill_version_id'],
                unique=False,
            )

    # Add composite index for jobs if it doesn't exist
    if not index_exists('jobs', 'ix_jobs_kind_status_created_at'):
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.create_index(
                'ix_jobs_kind_status_created_at',
                ['kind', 'status', 'created_at'],
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

    # Drop indexes if they exist
    if index_exists('jobs', 'ix_jobs_kind_status_created_at'):
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.drop_index('ix_jobs_kind_status_created_at')

    if index_exists('releases', 'ix_releases_skill_version_id'):
        with op.batch_alter_table('releases', schema=None) as batch_op:
            batch_op.drop_index('ix_releases_skill_version_id')

    if index_exists('audit_events', 'ix_audit_events_occurred_at'):
        with op.batch_alter_table('audit_events', schema=None) as batch_op:
            batch_op.drop_index('ix_audit_events_occurred_at')
