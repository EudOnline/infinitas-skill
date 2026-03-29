"""add private registry release graph

Revision ID: 20260329_0002
Revises: 20260329_0001
Create Date: 2026-03-29 00:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329_0002'
down_revision = '20260329_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'namespaces',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_namespaces_slug', 'namespaces', ['slug'], unique=True)

    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skills_namespace_id_slug', 'skills', ['namespace_id', 'slug'], unique=True)

    op.create_table(
        'skill_drafts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False, server_default='draft'),
        sa.Column('payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_drafts_skill_id_state', 'skill_drafts', ['skill_id', 'state'], unique=False)

    op.create_table(
        'skill_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_versions_skill_id_version', 'skill_versions', ['skill_id', 'version'], unique=True)

    op.create_table(
        'releases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('skill_version_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['skill_version_id'], ['skill_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_releases_skill_version_id_state', 'releases', ['skill_version_id', 'state'], unique=False)

    op.create_table(
        'artifacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=64), nullable=False),
        sa.Column('digest', sa.String(length=255), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_artifacts_release_id_kind_digest', 'artifacts', ['release_id', 'kind', 'digest'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_artifacts_release_id_kind_digest', table_name='artifacts')
    op.drop_table('artifacts')

    op.drop_index('ix_releases_skill_version_id_state', table_name='releases')
    op.drop_table('releases')

    op.drop_index('ix_skill_versions_skill_id_version', table_name='skill_versions')
    op.drop_table('skill_versions')

    op.drop_index('ix_skill_drafts_skill_id_state', table_name='skill_drafts')
    op.drop_table('skill_drafts')

    op.drop_index('ix_skills_namespace_id_slug', table_name='skills')
    op.drop_table('skills')

    op.drop_index('ix_namespaces_slug', table_name='namespaces')
    op.drop_table('namespaces')
