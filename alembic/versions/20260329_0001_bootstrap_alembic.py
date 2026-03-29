"""bootstrap alembic with compatibility tables

Revision ID: 20260329_0001
Revises:
Create Date: 2026-03-29 00:01:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='contributor'),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('light_bg_id', sa.String(length=64), nullable=True),
        sa.Column('dark_bg_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_token'), 'users', ['token'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table(
        'submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('skill_name', sa.String(length=200), nullable=False),
        sa.Column('publisher', sa.String(length=200), nullable=False, server_default='local'),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='draft'),
        sa.Column('payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('payload_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('status_log_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('review_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_submissions_skill_name'), 'submissions', ['skill_name'], unique=False)
    op.create_index(op.f('ix_submissions_status'), 'submissions', ['status'], unique=False)

    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='pending'),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reviews_status'), 'reviews', ['status'], unique=False)
    op.create_index(op.f('ix_reviews_submission_id'), 'reviews', ['submission_id'], unique=False)

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kind', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='queued'),
        sa.Column('payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('submission_id', sa.Integer(), nullable=True),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('log', sa.Text(), nullable=False, server_default=''),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jobs_kind'), 'jobs', ['kind'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_index(op.f('ix_jobs_submission_id'), 'jobs', ['submission_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_submission_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_kind'), table_name='jobs')
    op.drop_table('jobs')

    op.drop_index(op.f('ix_reviews_submission_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_status'), table_name='reviews')
    op.drop_table('reviews')

    op.drop_index(op.f('ix_submissions_status'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_skill_name'), table_name='submissions')
    op.drop_table('submissions')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_token'), table_name='users')
    op.drop_table('users')
