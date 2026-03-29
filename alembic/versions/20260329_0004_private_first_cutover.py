"""cut over to canonical private-first schema

Revision ID: 20260329_0004
Revises: 20260329_0003
Create Date: 2026-03-29 22:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0004"
down_revision: Union[str, None] = "20260329_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _drop_table_if_exists(name: str) -> None:
    if _has_table(name):
        op.drop_table(name)


def upgrade() -> None:
    for table_name in (
        "jobs",
        "access_credentials",
        "access_grants",
        "review_cases",
        "exposures",
        "artifacts",
        "releases",
        "skill_versions",
        "skill_drafts",
        "skills",
        "namespaces",
        "reviews",
        "submissions",
    ):
        _drop_table_if_exists(table_name)

    op.create_table(
        "principals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "slug", name="uq_principals_kind_slug"),
    )
    op.create_index("ix_principals_kind_slug", "principals", ["kind", "slug"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("principal_id"),
    )
    op.create_index("ix_teams_slug", "teams", ["slug"], unique=False)

    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_memberships_user_id_team_id", "team_memberships", ["user_id", "team_id"], unique=False)

    op.create_table(
        "service_principals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("principal_id"),
    )
    op.create_index("ix_service_principals_slug", "service_principals", ["slug"], unique=False)

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("namespace_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("default_visibility_profile", sa.String(length=64), nullable=True),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace_id", "slug", name="uq_skills_namespace_id_slug"),
    )
    op.create_index("ix_skills_namespace_id_slug", "skills", ["namespace_id", "slug"], unique=False)

    op.create_table(
        "skill_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("base_version_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("updated_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.ForeignKeyConstraint(["updated_by_principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=255), nullable=False),
        sa.Column("metadata_digest", sa.String(length=255), nullable=False),
        sa.Column("created_from_draft_id", sa.Integer(), nullable=True),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["created_from_draft_id"], ["skill_drafts.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_id_version"),
    )
    op.create_index("ix_skill_versions_skill_id_version", "skill_versions", ["skill_id", "version"], unique=False)

    op.create_table(
        "releases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_version_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("format_version", sa.String(length=32), nullable=False),
        sa.Column("manifest_artifact_id", sa.Integer(), nullable=True),
        sa.Column("bundle_artifact_id", sa.Integer(), nullable=True),
        sa.Column("signature_artifact_id", sa.Integer(), nullable=True),
        sa.Column("provenance_artifact_id", sa.Integer(), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["skill_version_id"], ["skill_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_version_id", name="uq_releases_skill_version_id"),
    )
    op.create_index("ix_releases_skill_version_id_state", "releases", ["skill_version_id", "state"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "exposures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("audience_type", sa.String(length=32), nullable=False),
        sa.Column("listing_mode", sa.String(length=32), nullable=False),
        sa.Column("install_mode", sa.String(length=32), nullable=False),
        sa.Column("review_requirement", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("requested_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("policy_snapshot_json", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.ForeignKeyConstraint(["requested_by_principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exposures_release_id_audience_type_state",
        "exposures",
        ["release_id", "audience_type", "state"],
        unique=False,
    )

    op.create_table(
        "review_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "review_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exposure_id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("opened_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exposure_id"], ["exposures.id"]),
        sa.ForeignKeyConstraint(["opened_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["review_policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_case_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_principal_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"]),
        sa.ForeignKeyConstraint(["reviewer_principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "access_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exposure_id", sa.Integer(), nullable=False),
        sa.Column("grant_type", sa.String(length=32), nullable=False),
        sa.Column("subject_ref", sa.String(length=255), nullable=False),
        sa.Column("constraints_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["exposure_id"], ["exposures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=True),
        sa.Column("grant_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("hashed_secret", sa.String(length=255), nullable=False),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("resource_selector_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grant_id"], ["access_grants.id"]),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credentials_principal_id_type_revoked_at_expires_at",
        "credentials",
        ["principal_id", "type", "revoked_at", "expires_at"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_ref", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("log", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_kind", "jobs", ["kind"], unique=False)
    op.create_index("ix_jobs_release_id", "jobs", ["release_id"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)


def downgrade() -> None:
    raise RuntimeError("private-first cutover migration is not reversible")
