"""add_composite_indexes

Revision ID: d7e124c31af2
Revises: 52ab6f2e589e
Create Date: 2026-06-01 14:30:25.957626
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = 'd7e124c31af2'
down_revision = '52ab6f2e589e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('review_cases', schema=None) as batch_op:
        batch_op.create_index(
            'ix_review_cases_exposure_id_state',
            ['exposure_id', 'state'],
            unique=False,
        )

    with op.batch_alter_table('access_grants', schema=None) as batch_op:
        batch_op.create_index(
            'ix_access_grants_exposure_id_grant_type_state',
            ['exposure_id', 'grant_type', 'state'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('access_grants', schema=None) as batch_op:
        batch_op.drop_index('ix_access_grants_exposure_id_grant_type_state')

    with op.batch_alter_table('review_cases', schema=None) as batch_op:
        batch_op.drop_index('ix_review_cases_exposure_id_state')
