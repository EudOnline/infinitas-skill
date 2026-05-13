from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.models import Exposure, RegistryObject
from server.modules.access.authn import AccessContext
from server.ui.formatting import humanize_timestamp, load_json_list, load_json_object
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
    object_id: int,
    skill_id: int | None,
) -> dict[str, Any] | None:
    releases = scope.releases_by_object_id.get(object_id, [])
    if not releases:
        return None
    release = releases[0]
    version_label = None
    if skill_id is not None:
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


def type_details(scope: LibraryScope, registry_object: RegistryObject) -> dict[str, Any]:
    if registry_object.kind == "agent_preset":
        spec = scope.preset_specs_by_object_id.get(registry_object.id)
        if spec is None:
            return {"kind": "agent_preset"}
        return {
            "kind": "agent_preset",
            "runtime_family": spec.runtime_family,
            "supported_memory_modes": load_json_list(spec.supported_memory_modes_json),
            "default_memory_mode": spec.default_memory_mode,
            "pinned_skill_dependencies": load_json_list(spec.pinned_skill_dependencies_json),
        }
    if registry_object.kind == "agent_code":
        spec = scope.code_specs_by_object_id.get(registry_object.id)
        if spec is None:
            return {"kind": "agent_code"}
        return {
            "kind": "agent_code",
            "runtime_family": spec.runtime_family,
            "language": spec.language,
            "entrypoint": spec.entrypoint,
            "external_source": load_json_object(spec.external_source_json),
        }
    skill = scope.skills_by_object_id.get(registry_object.id)
    return {
        "kind": "skill",
        "default_visibility_profile": (
            skill.default_visibility_profile if skill is not None else None
        ),
    }


def object_payload(scope: LibraryScope, registry_object: RegistryObject) -> dict[str, Any]:
    skill = scope.skills_by_object_id.get(registry_object.id)
    current_release = current_release_payload(
        scope,
        object_id=registry_object.id,
        skill_id=skill.id if skill is not None else None,
    )
    release_id = current_release["release_id"] if current_release is not None else None
    current_exposure = None
    if release_id is not None:
        exposures = scope.exposures_by_release_id.get(int(release_id), [])
        current_exposure = exposures[0] if exposures else None

    share_link_count = 0
    token_count = 0
    for release in scope.releases_by_object_id.get(registry_object.id, []):
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
        "id": registry_object.id,
        "kind": registry_object.kind,
        "slug": registry_object.slug,
        "display_name": registry_object.display_name,
        "summary": registry_object.summary or "",
        "updated_at": humanize_timestamp(iso_stamp(registry_object.updated_at)),
        "current_release": current_release,
        "current_visibility": visibility_payload(current_exposure),
        "token_count": token_count,
        "share_link_count": share_link_count,
    }


def list_library_objects(db: Session, *, actor: AccessContext) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return [object_payload(scope, item) for item in scope.objects]


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
    registry_object = next((item for item in scope.objects if item.id == object_id), None)
    if registry_object is None:
        return None
    return {
        "object": object_payload(scope, registry_object),
        "details": type_details(scope, registry_object),
        "releases": list_library_releases_from_scope(scope, object_id=object_id),
    }
