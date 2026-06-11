"""add_fk_constraints_and_indexes

Revision ID: d4e5f6a7b8c9
Revises: c8f3e21d4a8b
Create Date: 2026-06-11 10:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c8f3e21d4a8b'
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

    def fk_exists(table_name, fk_name):
        try:
            existing_fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name) if fk.get('name')]
            return fk_name in existing_fks
        except Exception:
            return False

    # --- Release table: add FK constraints to artifact columns ---
    with op.batch_alter_table('releases', schema=None) as batch_op:
        if not fk_exists('releases', 'fk_releases_manifest_artifact_id'):
            batch_op.create_foreign_key(
                'fk_releases_manifest_artifact_id',
                'artifacts',
                ['manifest_artifact_id'],
                ['id'],
                ondelete='SET NULL',
            )
        if not fk_exists('releases', 'fk_releases_bundle_artifact_id'):
            batch_op.create_foreign_key(
                'fk_releases_bundle_artifact_id',
                'artifacts',
                ['bundle_artifact_id'],
                ['id'],
                ondelete='SET NULL',
            )
        if not fk_exists('releases', 'fk_releases_signature_artifact_id'):
            batch_op.create_foreign_key(
                'fk_releases_signature_artifact_id',
                'artifacts',
                ['signature_artifact_id'],
                ['id'],
                ondelete='SET NULL',
            )
        if not fk_exists('releases', 'fk_releases_provenance_artifact_id'):
            batch_op.create_foreign_key(
                'fk_releases_provenance_artifact_id',
                'artifacts',
                ['provenance_artifact_id'],
                ['id'],
                ondelete='SET NULL',
            )

    # --- Release table: add index on created_by_principal_id ---
    if not index_exists('releases', 'ix_releases_created_by_principal_id'):
        with op.batch_alter_table('releases', schema=None) as batch_op:
            batch_op.create_index(
                'ix_releases_created_by_principal_id',
                ['created_by_principal_id'],
                unique=False,
            )

    # --- SkillDraft table: add indexes on FK columns ---
    if not index_exists('skill_drafts', 'ix_skill_drafts_base_version_id'):
        with op.batch_alter_table('skill_drafts', schema=None) as batch_op:
            batch_op.create_index(
                'ix_skill_drafts_base_version_id',
                ['base_version_id'],
                unique=False,
            )

    if not index_exists('skill_drafts', 'ix_skill_drafts_content_artifact_id'):
        with op.batch_alter_table('skill_drafts', schema=None) as batch_op:
            batch_op.create_index(
                'ix_skill_drafts_content_artifact_id',
                ['content_artifact_id'],
                unique=False,
            )

    # --- SkillVersion table: add indexes on FK columns ---
    if not index_exists('skill_versions', 'ix_skill_versions_created_from_draft_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.create_index(
                'ix_skill_versions_created_from_draft_id',
                ['created_from_draft_id'],
                unique=False,
            )

    if not index_exists('skill_versions', 'ix_skill_versions_created_by_principal_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.create_index(
                'ix_skill_versions_created_by_principal_id',
                ['created_by_principal_id'],
                unique=False,
            )

    # --- AuditEvent table: add composite index for aggregate queries ---
    if not index_exists('audit_events', 'ix_audit_events_aggregate_type_aggregate_id'):
        with op.batch_alter_table('audit_events', schema=None) as batch_op:
            batch_op.create_index(
                'ix_audit_events_aggregate_type_aggregate_id',
                ['aggregate_type', 'aggregate_id'],
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

    # Drop indexes in reverse order
    if index_exists('audit_events', 'ix_audit_events_aggregate_type_aggregate_id'):
        with op.batch_alter_table('audit_events', schema=None) as batch_op:
            batch_op.drop_index('ix_audit_events_aggregate_type_aggregate_id')

    if index_exists('skill_versions', 'ix_skill_versions_created_by_principal_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.drop_index('ix_skill_versions_created_by_principal_id')

    if index_exists('skill_versions', 'ix_skill_versions_created_from_draft_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.drop_index('ix_skill_versions_created_from_draft_id')

    if index_exists('skill_drafts', 'ix_skill_drafts_content_artifact_id'):
        with op.batch_alter_table('skill_drafts', schema=None) as batch_op:
            batch_op.drop_index('ix_skill_drafts_content_artifact_id')

    if index_exists('skill_drafts', 'ix_skill_drafts_base_version_id'):
        with op.batch_alter_table('skill_drafts', schema=None) as batch_op:
            batch_op.drop_index('ix_skill_drafts_base_version_id')

    if index_exists('releases', 'ix_releases_created_by_principal_id'):
        with op.batch_alter_table('releases', schema=None) as batch_op:
            batch_op.drop_index('ix_releases_created_by_principal_id')

    # Drop FK constraints from releases
    with op.batch_alter_table('releases', schema=None) as batch_op:
        batch_op.drop_constraint('fk_releases_provenance_artifact_id', type_='foreignkey')
        batch_op.drop_constraint('fk_releases_signature_artifact_id', type_='foreignkey')
        batch_op.drop_constraint('fk_releases_bundle_artifact_id', type_='foreignkey')
        batch_op.drop_constraint('fk_releases_manifest_artifact_id', type_='foreignkey')
