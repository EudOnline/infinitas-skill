"""cut personal auth over to hashed credentials

Revision ID: 20260329_0005
Revises: 20260329_0004
Create Date: 2026-03-29 23:45:00
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0005"
down_revision: Union[str, None] = "20260329_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TOKEN_HASH_PREFIX = "sha256:"
DEFAULT_PERSONAL_SCOPES = json.dumps(["api:user", "session:user"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{TOKEN_HASH_PREFIX}{digest}"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "token",
            existing_type=sa.String(length=255),
            nullable=True,
        )

    bind = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("username", sa.String(length=100)),
        sa.column("display_name", sa.String(length=200)),
        sa.column("token", sa.String(length=255)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    principals = sa.table(
        "principals",
        sa.column("id", sa.Integer()),
        sa.column("kind", sa.String(length=32)),
        sa.column("slug", sa.String(length=200)),
        sa.column("display_name", sa.String(length=200)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    credentials = sa.table(
        "credentials",
        sa.column("id", sa.Integer()),
        sa.column("principal_id", sa.Integer()),
        sa.column("grant_id", sa.Integer()),
        sa.column("type", sa.String(length=64)),
        sa.column("hashed_secret", sa.String(length=255)),
        sa.column("scopes_json", sa.Text()),
        sa.column("resource_selector_json", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    # Normalize any transitional plaintext credential rows so runtime auth can
    # verify hashes only after this cutover lands.
    credential_rows = bind.execute(
        sa.select(
            credentials.c.id,
            credentials.c.hashed_secret,
        ).where(
            credentials.c.hashed_secret.is_not(None),
        )
    ).mappings()
    for row in credential_rows:
        stored = str(row["hashed_secret"] or "").strip()
        if not stored or stored.startswith(TOKEN_HASH_PREFIX):
            continue
        bind.execute(
            credentials.update()
            .where(credentials.c.id == row["id"])
            .values(hashed_secret=_hash_token(stored))
        )

    now = _utcnow()
    user_rows = bind.execute(
        sa.select(
            users.c.id,
            users.c.username,
            users.c.display_name,
            users.c.token,
        ).where(
            users.c.token.is_not(None),
        )
    ).mappings()
    for row in user_rows:
        raw_token = str(row["token"] or "").strip()
        if not raw_token:
            continue

        principal_id = bind.execute(
            sa.select(principals.c.id).where(
                principals.c.kind == "user",
                principals.c.slug == row["username"],
            )
        ).scalar_one_or_none()
        if principal_id is None:
            bind.execute(
                principals.insert().values(
                    kind="user",
                    slug=row["username"],
                    display_name=row["display_name"],
                    created_at=now,
                    updated_at=now,
                )
            )
            principal_id = bind.execute(
                sa.select(principals.c.id).where(
                    principals.c.kind == "user",
                    principals.c.slug == row["username"],
                )
            )
            principal_id = principal_id.scalar_one()

        credential_row = bind.execute(
            sa.select(credentials.c.id, credentials.c.scopes_json).where(
                credentials.c.principal_id == principal_id,
                credentials.c.type == "personal_token",
            )
        ).mappings().first()
        if credential_row is None:
            bind.execute(
                credentials.insert().values(
                    principal_id=principal_id,
                    grant_id=None,
                    type="personal_token",
                    hashed_secret=_hash_token(raw_token),
                    scopes_json=DEFAULT_PERSONAL_SCOPES,
                    resource_selector_json="{}",
                    created_at=now,
                )
            )
        else:
            next_scopes = credential_row["scopes_json"] or DEFAULT_PERSONAL_SCOPES
            bind.execute(
                credentials.update()
                .where(credentials.c.id == credential_row["id"])
                .values(
                    hashed_secret=_hash_token(raw_token),
                    scopes_json=next_scopes,
                )
            )

    bind.execute(
        users.update()
        .where(users.c.token.is_not(None))
        .values(
            token=None,
            updated_at=now,
        )
    )


def downgrade() -> None:
    raise RuntimeError("personal token hash cutover is not reversible")
