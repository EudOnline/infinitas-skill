from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

import server.modules.identity.service as identity_service
from server.i18n import with_lang
from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant
from server.modules.identity.models import Credential
from server.modules.library.queries import (
    LibraryScope,
    iso_stamp,
    iter_grant_credentials,
    load_library_scope,
    parse_datetime,
)
from server.modules.shared.formatting import humanize_timestamp
from server.modules.shared.json import loads_json_object as load_json_object


def credential_state(credential: Credential, grant: AccessGrant | None = None) -> str:
    now = datetime.now(timezone.utc)
    if credential.revoked_at is not None:
        return "revoked"
    expires_at = parse_datetime(credential.expires_at)
    if expires_at is not None and expires_at <= now:
        return "expired"
    if grant is not None and grant.state and grant.state != "active":
        return grant.state
    return "active"


def grant_state(grant: AccessGrant, constraints: dict[str, Any]) -> str:
    if grant.state and grant.state != "active":
        return grant.state
    expires_at = parse_datetime(grant.expires_at)
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "active"


def credential_is_active(credential: Credential, grant: AccessGrant | None = None) -> bool:
    return credential_state(credential, grant) == "active"


def grant_is_active(grant: AccessGrant, constraints: dict[str, Any]) -> bool:
    return grant_state(grant, constraints) == "active"


def credential_is_share_secret(credential: Credential) -> bool:
    return credential.type in {"share_password", "share_capability"}


def token_type_for_credential(credential: Credential) -> str:
    return identity_service.token_type_for_scopes(credential.scopes_json)


def build_token_rows_from_scope(
    scope: LibraryScope,
    *,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for skill, release, version, _exposure, grant, credential in iter_grant_credentials(
        scope, object_id=object_id, grant_type="token"
    ):
        if credential_is_share_secret(credential):
            continue
        constraints = load_json_object(grant.constraints_json)
        state = credential_state(credential, grant)
        revoked_at = parse_datetime(credential.revoked_at)
        sort_at = (
            revoked_at
            or parse_datetime(credential.last_used_at)
            or parse_datetime(credential.created_at)
        )
        token_type = token_type_for_credential(credential)
        label = str(constraints.get("label") or "").strip() or None
        rows.append(
            {
                "id": credential.id,
                "credential_id": credential.id,
                "token_type": token_type,
                "type": token_type,
                "object_id": skill.id,
                "object_name": skill.display_name,
                "object_href": with_lang(f"/library/{skill.id}", lang),
                "release_id": release.id,
                "release_version": version.version if version is not None else None,
                "label": label,
                "agent_name": label,
                "grant_id": grant.id,
                "state": state,
                "can_revoke": state == "active",
                "created_at": humanize_timestamp(iso_stamp(credential.created_at)),
                "created": humanize_timestamp(iso_stamp(credential.created_at)),
                "last_used_at": humanize_timestamp(iso_stamp(credential.last_used_at)),
                "revoked_at": humanize_timestamp(iso_stamp(credential.revoked_at)),
                "_sort_at": sort_at or datetime.min.replace(tzinfo=timezone.utc),
            }
        )
    rows.sort(key=lambda item: item["_sort_at"], reverse=True)
    return rows


def list_library_token_rows(
    db: Session,
    *,
    actor: AccessContext,
    lang: str,
    object_id: int | None = None,
    scope: LibraryScope | None = None,
) -> list[dict[str, Any]]:
    if scope is None:
        scope, _total = load_library_scope(db, actor=actor)
    return build_token_rows_from_scope(scope, lang=lang, object_id=object_id)
