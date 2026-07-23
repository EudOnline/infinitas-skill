"""Read-only version comparison models for the human Library UI."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.authoring.models import SkillVersion
from server.modules.library.projections import object_payload
from server.modules.library.queries import load_library_scope
from server.modules.shared.formatting import iso_format
from server.modules.shared.json import loads_json_object


def _version_view(version: SkillVersion) -> dict[str, Any]:
    manifest = loads_json_object(version.sealed_manifest_json)
    metadata = manifest.get("metadata")
    return {
        "id": version.id,
        "version": version.version,
        "content_digest": version.content_digest,
        "metadata_digest": version.metadata_digest,
        "created_at": iso_format(version.created_at) or "-",
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def compare_library_versions(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
    left: str,
    right: str,
) -> dict[str, Any] | None:
    scope, _total = load_library_scope(db, actor=actor)
    skill = next((item for item in scope.skills if item.id == object_id), None)
    if skill is None:
        return None
    versions = scope.versions_by_skill_id.get(object_id, [])
    by_label = {item.version: item for item in versions}
    left_model = by_label.get(left)
    right_model = by_label.get(right)
    if left_model is None or right_model is None:
        return None
    left_view = _version_view(left_model)
    right_view = _version_view(right_model)
    left_metadata = left_view["metadata"]
    right_metadata = right_view["metadata"]
    changed_fields = [
        {
            "name": key,
            "left": left_metadata.get(key),
            "right": right_metadata.get(key),
        }
        for key in sorted(set(left_metadata) | set(right_metadata))
        if left_metadata.get(key) != right_metadata.get(key)
    ]
    return {
        "object": object_payload(scope, skill),
        "left": left_view,
        "right": right_view,
        "content_changed": left_model.content_digest != right_model.content_digest,
        "metadata_changed": left_model.metadata_digest != right_model.metadata_digest,
        "changed_fields": changed_fields,
        "versions": [item.version for item in versions],
    }
