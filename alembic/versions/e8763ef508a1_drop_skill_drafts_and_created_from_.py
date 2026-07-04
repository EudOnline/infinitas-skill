"""drop skill_drafts and created_from_draft_id

Revision ID: e8763ef508a1
Revises: 6fe6c7710a23
Create Date: 2026-07-04 15:46:38.750623
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e8763ef508a1'
down_revision = '6fe6c7710a23'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy import inspect
    conn = op.get_bind()
    return table_name in inspect(conn).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy import inspect
    conn = op.get_bind()
    columns = {col['name'] for col in inspect(conn).get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    # Drop the column (and its index/foreign-key constraint) first so
    # skill_versions no longer references skill_drafts before the draft table is removed.
    if _column_exists('skill_versions', 'created_from_draft_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.drop_index(op.f('ix_skill_versions_created_from_draft_id'))
            batch_op.drop_column('created_from_draft_id')

    if _table_exists('skill_drafts'):
        op.drop_index(op.f('ix_skill_drafts_base_version_id'), table_name='skill_drafts')
        op.drop_index(op.f('ix_skill_drafts_content_artifact_id'), table_name='skill_drafts')
        op.drop_table('skill_drafts')


def downgrade() -> None:
    if not _column_exists('skill_versions', 'created_from_draft_id'):
        with op.batch_alter_table('skill_versions', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('created_from_draft_id', sa.INTEGER(), nullable=True)
            )
            batch_op.create_index(
                op.f('ix_skill_versions_created_from_draft_id'),
                ['created_from_draft_id'],
                unique=False,
            )
            batch_op.create_foreign_key(
                'fk_skill_versions_created_from_draft_id',
                'skill_drafts',
                ['created_from_draft_id'],
                ['id'],
            )

    if not _table_exists('skill_drafts'):
        op.create_table(
            'skill_drafts',
            sa.Column('id', sa.INTEGER(), nullable=False),
            sa.Column('skill_id', sa.INTEGER(), nullable=False),
            sa.Column('base_version_id', sa.INTEGER(), nullable=True),
            sa.Column('state', sa.VARCHAR(length=32), nullable=False),
            sa.Column('content_ref', sa.TEXT(), nullable=False),
            sa.Column('metadata_json', sa.TEXT(), nullable=False),
            sa.Column('updated_by_principal_id', sa.INTEGER(), nullable=True),
            sa.Column('updated_at', sa.DATETIME(), nullable=False),
            sa.Column(
                'content_mode',
                sa.VARCHAR(length=32),
                server_default=sa.text("'external_ref'"),
                nullable=False,
            ),
            sa.Column('content_artifact_id', sa.INTEGER(), nullable=True),
            sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
            sa.ForeignKeyConstraint(['updated_by_principal_id'], ['principals.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            op.f('ix_skill_drafts_content_artifact_id'),
            'skill_drafts',
            ['content_artifact_id'],
            unique=False,
        )
        op.create_index(
            op.f('ix_skill_drafts_base_version_id'),
            'skill_drafts',
            ['base_version_id'],
            unique=False,
        )
