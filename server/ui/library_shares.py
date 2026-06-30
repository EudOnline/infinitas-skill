from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from server.models import AccessGrant
from server.modules.access.authn import AccessContext
from server.ui.formatting import humanize_timestamp, load_json_object
from server.ui.i18n import with_lang
from server.ui.library_access import (
    credential_is_share_secret,
    grant_is_active,
    grant_state,
)
from server.ui.library_scope import (
    LibraryScope,
    iso_stamp,
    iter_grant_credentials,
    load_library_scope,
    parse_datetime,
)


def share_link_state_from_grant(grant: AccessGrant, constraints: dict[str, Any]) -> str:
    base = grant_state(grant, constraints)
    if base != "active":
        return base
    usage_limit = share_usage_limit(constraints)
    if usage_limit is not None and share_usage_count(constraints) >= usage_limit:
        return "exhausted"
    return "active"


def share_label(constraints: dict[str, Any]) -> str:
    return str(constraints.get("label") or constraints.get("name") or "")


def share_usage_count(constraints: dict[str, Any]) -> int:
    return int(constraints.get("usage_count", constraints.get("used_count") or 0) or 0)


def share_usage_limit(constraints: dict[str, Any]) -> int | None:
    usage_limit = constraints.get("usage_limit", constraints.get("max_uses"))
    return int(usage_limit) if usage_limit is not None else None


def build_share_rows_from_scope(
    scope: LibraryScope,
    *,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_grants: set[int] = set()
    for skill, release, version, _exposure, grant, credential in iter_grant_credentials(
        scope, object_id=object_id, grant_type="link"
    ):
        if grant.id in seen_grants:
            continue
        seen_grants.add(grant.id)
        constraints = load_json_object(grant.constraints_json)
        credentials = scope.credentials_by_grant_id.get(grant.id, [])
        rows.append(
            {
                "id": grant.id,
                "object_id": skill.id,
                "object_name": skill.display_name,
                "object_href": with_lang(f"/library/{skill.id}", lang),
                "release_id": release.id,
                "release_version": version.version if version is not None else None,
                "label": share_label(constraints),
                "expiry": humanize_timestamp(constraints.get("expires_at")),
                "has_password": bool(
                    constraints.get("temporary_password")
                    or constraints.get("password")
                    or any(credential_is_share_secret(item) for item in credentials)
                ),
                "usage_count": share_usage_count(constraints),
                "usage_limit": share_usage_limit(constraints),
                "state": share_link_state_from_grant(grant, constraints),
                "can_revoke": grant_is_active(grant, constraints),
                "created": humanize_timestamp(iso_stamp(grant.created_at)),
                "created_at": humanize_timestamp(iso_stamp(grant.created_at)),
                "_sort_at": parse_datetime(grant.created_at)
                or datetime.min.replace(tzinfo=timezone.utc),
            }
        )
    rows.sort(key=lambda item: item["_sort_at"], reverse=True)
    return rows


def list_library_share_rows(
    db: Session,
    *,
    actor: AccessContext,
    lang: str,
    object_id: int | None = None,
    scope: LibraryScope | None = None,
) -> list[dict[str, Any]]:
    if scope is None:
        scope, _total = load_library_scope(db, actor=actor)
    return build_share_rows_from_scope(scope, lang=lang, object_id=object_id)
