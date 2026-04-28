"""add product token metadata and share links

Revision ID: 20260424_0001
Revises: 20260419_0007
Create Date: 2026-04-24 19:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260424_0001"
down_revision: Union[str, None] = "20260419_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.add_column(
            sa.Column("product_token_name", sa.String(length=200), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("product_token_type", sa.String(length=32), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("product_scope_type", sa.String(length=32), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("product_scope_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("issued_for", sa.String(length=200), nullable=False, server_default="")
        )
        batch_op.create_index("ix_credentials_product_scope_id", ["product_scope_id"], unique=False)

    op.create_table(
        "share_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_principal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_share_links_release_id", "share_links", ["release_id"], unique=False)
    op.create_index("ix_share_links_slug", "share_links", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_share_links_slug", table_name="share_links")
    op.drop_index("ix_share_links_release_id", table_name="share_links")
    op.drop_table("share_links")

    with op.batch_alter_table("credentials") as batch_op:
        batch_op.drop_index("ix_credentials_product_scope_id")
        batch_op.drop_column("issued_for")
        batch_op.drop_column("product_scope_id")
        batch_op.drop_column("product_scope_type")
        batch_op.drop_column("product_token_type")
        batch_op.drop_column("product_token_name")
