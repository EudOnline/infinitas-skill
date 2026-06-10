from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.models import Exposure, Skill
from server.modules.access.authn import AccessContext
from server.ui.formatting import humanize_timestamp, load_json_object
from server.ui.library_access import (
    credential_is_active,
    credential_is_share_secret,
    grant_is_active,
)
from server.ui.library_scope import LibraryScope, iso_stamp, load_library_scope


def visibility_payload(exposure: Exposure | None) -> dict[str, Any]:
    if exposure is None:
        return {
            "audience_type": None,
            "listing_mode": None,
            "install_mode": None,
            "state": None,
        }
    return {
        "audience_type": exposure.audience_type,
        "listing_mode": exposure.listing_mode,
        "install_mode": exposure.install_mode,
        "state": exposure.state,
    }


def current_release_payload(
    scope: LibraryScope,
    *,
    skill_id: int,
) -> dict[str, Any] | None:
    releases = scope.releases_by_skill_id.get(skill_id, [])
    if not releases:
        return None
    release = releases[0]
    version_label = None
    versions = scope.versions_by_skill_id.get(skill_id, [])
    version_map = {version.id: version for version in versions}
    version = version_map.get(release.skill_version_id)
    if version is not None:
        version_label = version.version
    return {
        "release_id": release.id,
        "version": version_label,
        "state": release.state,
        "ready_at": iso_stamp(release.ready_at),
    }


def type_details(scope: LibraryScope, skill: Skill) -> dict[str, Any]:
    return {
        "kind": "skill",
        "default_visibility_profile": skill.default_visibility_profile,
    }


def object_payload(scope: LibraryScope, skill: Skill) -> dict[str, Any]:
    current_release = current_release_payload(
        scope,
        skill_id=skill.id,
    )
    release_id = current_release["release_id"] if current_release is not None else None
    current_exposure = None
    if release_id is not None:
        exposures = scope.exposures_by_release_id.get(int(release_id), [])
        current_exposure = exposures[0] if exposures else None

    share_link_count = 0
    token_count = 0
    for release in scope.releases_by_skill_id.get(skill.id, []):
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            grants = scope.grants_by_exposure_id.get(exposure.id, [])
            for grant in grants:
                if grant.grant_type == "link":
                    if grant_is_active(grant, load_json_object(grant.constraints_json)):
                        share_link_count += 1
                    continue
                for credential in scope.credentials_by_grant_id.get(grant.id, []):
                    if credential_is_share_secret(credential):
                        continue
                    if credential_is_active(credential, grant):
                        token_count += 1

    return {
        "id": skill.id,
        "kind": "skill",
        "slug": skill.slug,
        "display_name": skill.display_name,
        "summary": skill.summary or "",
        "updated_at": humanize_timestamp(iso_stamp(skill.updated_at)),
        "current_release": current_release,
        "current_visibility": visibility_payload(current_exposure),
        "token_count": token_count,
        "share_link_count": share_link_count,
    }


def list_library_objects(db: Session, *, actor: AccessContext) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return [object_payload(scope, item) for item in scope.skills]


def get_library_object_detail(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
    scope: LibraryScope | None = None,
) -> dict[str, Any] | None:
    from server.ui.library_releases import list_library_releases_from_scope

    if scope is None:
        scope = load_library_scope(db, actor=actor)
    skill = next((item for item in scope.skills if item.id == object_id), None)
    if skill is None:
        return None
    return {
        "object": object_payload(scope, skill),
        "details": type_details(scope, skill),
        "releases": list_library_releases_from_scope(scope, skill_id=object_id),
    }
