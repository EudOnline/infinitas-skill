"""remove_registry_object_abstraction

Remove the RegistryObject polymorphic layer: migrate Release FK from
registry_object_id to skill_id, drop object_kind from releases,
drop registry_object_id from skills, and drop the registry_objects,
agent_code_specs, and agent_preset_specs tables.

Revision ID: a1b2c3d4e5f6
Revises: cddf6871f17d
Create Date: 2026-06-02 12:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'cddf6871f17d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up any stale Alembic temp tables from prior migrations (SQLite batch mode).
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_releases")
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_skills")

    # Step 1: Single batch on releases — add skill_id, drop old columns and indexes
    with op.batch_alter_table('releases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('skill_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_releases_skill_id', 'skills', ['skill_id'], ['id'])
        batch_op.create_index('ix_releases_skill_id', ['skill_id'], unique=False)
        batch_op.drop_index('ix_releases_registry_object_id')
        batch_op.drop_column('object_kind')
        batch_op.drop_column('registry_object_id')

    # Step 2: Populate skill_id from skill_versions -> skill chain
    op.execute(
        """
        UPDATE releases
        SET skill_id = (
            SELECT sv.skill_id
            FROM skill_versions sv
            WHERE sv.id = releases.skill_version_id
        )
        WHERE releases.skill_id IS NULL
        """
    )

    # Step 3: Drop registry_object_id from skills
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_skills")
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_index('ix_skills_registry_object_id')
        batch_op.drop_column('registry_object_id')

    # Step 4: Drop spec tables (may not exist if already removed)
    op.execute("DROP TABLE IF EXISTS agent_preset_specs")
    op.execute("DROP TABLE IF EXISTS agent_code_specs")

    # Step 5: Drop registry_objects table
    op.execute("DROP TABLE IF EXISTS registry_objects")


def downgrade() -> None:
    raise NotImplementedError("Cannot reverse registry object abstraction removal")
