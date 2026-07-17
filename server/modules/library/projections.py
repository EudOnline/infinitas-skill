from __future__ import annotations

from server.i18n import with_lang
from server.modules.authoring.models import Skill
from server.modules.exposure.models import Exposure
from server.modules.library.access import (
    credential_is_active,
    credential_is_share_secret,
)
from server.modules.library.queries import (
    LibraryScope,
    iso_stamp,
    iter_grant_credentials,
)
from server.modules.library.read_models import (
    CurrentReleaseReadModel,
    LibraryObjectReadModel,
    LibraryObjectTypeDetailsReadModel,
    VisibilityReadModel,
)
from server.modules.shared.formatting import humanize_timestamp


def visibility_payload(exposure: Exposure | None) -> VisibilityReadModel:
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
) -> CurrentReleaseReadModel | None:
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


def type_details(scope: LibraryScope, skill: Skill) -> LibraryObjectTypeDetailsReadModel:
    return {
        "kind": "skill",
        "default_visibility_profile": skill.default_visibility_profile,
    }


def object_payload(
    scope: LibraryScope, skill: Skill, *, lang: str | None = None
) -> LibraryObjectReadModel:
    current_release = current_release_payload(scope, skill_id=skill.id)
    release_id = current_release["release_id"] if current_release is not None else None
    current_exposure = None
    if release_id is not None:
        exposures = scope.exposures_by_release_id.get(int(release_id), [])
        current_exposure = exposures[0] if exposures else None

    share_link_count = 0
    token_count = 0
    for _skill, _release, _version, _exposure, grant, credential in iter_grant_credentials(
        scope, object_id=skill.id
    ):
        if grant.grant_type == "link":
            if credential_is_active(credential, grant):
                share_link_count += 1
        elif not credential_is_share_secret(credential) and credential_is_active(credential, grant):
            token_count += 1

    detail_href = with_lang(f"/library/{skill.id}", lang) if lang else f"/library/{skill.id}"
    return {
        "id": skill.id,
        "kind": "skill",
        "slug": skill.slug,
        "name": skill.display_name,
        "display_name": skill.display_name,
        "summary": skill.summary or "",
        "updated_at": humanize_timestamp(iso_stamp(skill.updated_at)),
        "current_release": current_release,
        "version": current_release["version"] if current_release is not None else None,
        "current_visibility": visibility_payload(current_exposure),
        "token_count": token_count,
        "share_link_count": share_link_count,
        "detail_href": detail_href,
    }
