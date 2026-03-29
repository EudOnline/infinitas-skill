"""add exposure review and access policy tables

Revision ID: 20260329_0003
Revises: 20260329_0002
Create Date: 2026-03-29 01:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329_0003'
down_revision = '20260329_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'exposures',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='private'),
        sa.Column('review_requirement', sa.String(length=32), nullable=False, server_default='none'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exposures_release_id_mode', 'exposures', ['release_id', 'mode'], unique=False)

    op.create_table(
        'review_cases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exposure_id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exposure_id'], ['exposures.id']),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_cases_exposure_id_status', 'review_cases', ['exposure_id', 'status'], unique=False)

    op.create_table(
        'access_grants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exposure_id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exposure_id'], ['exposures.id']),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_access_grants_release_id', 'access_grants', ['release_id'], unique=False)

    op.create_table(
        'access_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('grant_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['grant_id'], ['access_grants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_access_credentials_token', 'access_credentials', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_access_credentials_token', table_name='access_credentials')
    op.drop_table('access_credentials')

    op.drop_index('ix_access_grants_release_id', table_name='access_grants')
    op.drop_table('access_grants')

    op.drop_index('ix_review_cases_exposure_id_status', table_name='review_cases')
    op.drop_table('review_cases')

    op.drop_index('ix_exposures_release_id_mode', table_name='exposures')
    op.drop_table('exposures')
