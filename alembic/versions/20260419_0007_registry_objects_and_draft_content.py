"""add shared registry objects and durable draft content metadata

Revision ID: 20260419_0007
Revises: 5b144d756fe3
Create Date: 2026-04-19 10:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260419_0007"
down_revision: Union[str, None] = "5b144d756fe3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registry_objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("namespace_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("default_visibility_profile", sa.String(length=64), nullable=True),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["namespace_id"], ["principals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "namespace_id",
            "kind",
            "slug",
            name="uq_registry_objects_namespace_id_kind_slug",
        ),
    )
    op.create_index(
        "ix_registry_objects_namespace_id_kind_slug",
        "registry_objects",
        ["namespace_id", "kind", "slug"],
        unique=False,
    )

    op.create_table(
        "agent_preset_specs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registry_object_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("runtime_family", sa.String(length=64), nullable=False, server_default="openclaw"),
        sa.Column("supported_memory_modes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("default_memory_mode", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("pinned_skill_dependencies_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("default_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("default_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("default_tools_json", sa.Text(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["registry_object_id"], ["registry_objects.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registry_object_id"),
        sa.UniqueConstraint("skill_id"),
    )

    op.create_table(
        "agent_code_specs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registry_object_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("runtime_family", sa.String(length=64), nullable=False, server_default="openclaw"),
        sa.Column("language", sa.String(length=64), nullable=False, server_default="python"),
        sa.Column("entrypoint", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("external_source_json", sa.Text(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["registry_object_id"], ["registry_objects.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registry_object_id"),
        sa.UniqueConstraint("skill_id"),
    )

    with op.batch_alter_table("skills") as batch_op:
        batch_op.add_column(sa.Column("registry_object_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_skills_registry_object_id_registry_objects",
            "registry_objects",
            ["registry_object_id"],
            ["id"],
        )
        batch_op.create_index("ix_skills_registry_object_id", ["registry_object_id"], unique=False)

    with op.batch_alter_table("skill_drafts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "content_mode",
                sa.String(length=32),
                nullable=False,
                server_default="external_ref",
            )
        )
        batch_op.add_column(sa.Column("content_artifact_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("skill_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sealed_manifest_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            )
        )

    with op.batch_alter_table("releases") as batch_op:
        batch_op.add_column(sa.Column("registry_object_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "object_kind",
                sa.String(length=64),
                nullable=False,
                server_default="skill",
            )
        )
        batch_op.create_foreign_key(
            "fk_releases_registry_object_id_registry_objects",
            "registry_objects",
            ["registry_object_id"],
            ["id"],
        )
        batch_op.create_index("ix_releases_registry_object_id", ["registry_object_id"], unique=False)

    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.alter_column(
            "release_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.alter_column(
            "release_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    with op.batch_alter_table("releases") as batch_op:
        batch_op.drop_index("ix_releases_registry_object_id")
        batch_op.drop_constraint("fk_releases_registry_object_id_registry_objects", type_="foreignkey")
        batch_op.drop_column("object_kind")
        batch_op.drop_column("registry_object_id")

    with op.batch_alter_table("skill_versions") as batch_op:
        batch_op.drop_column("sealed_manifest_json")

    with op.batch_alter_table("skill_drafts") as batch_op:
        batch_op.drop_column("content_artifact_id")
        batch_op.drop_column("content_mode")

    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_index("ix_skills_registry_object_id")
        batch_op.drop_constraint("fk_skills_registry_object_id_registry_objects", type_="foreignkey")
        batch_op.drop_column("registry_object_id")

    op.drop_table("agent_code_specs")
    op.drop_table("agent_preset_specs")
    op.drop_index("ix_registry_objects_namespace_id_kind_slug", table_name="registry_objects")
    op.drop_table("registry_objects")
