from __future__ import annotations

from server.models import AccessCredential
from server.modules.registry.service import visible_registry_request_paths
from server.settings import get_settings


def credential_can_read_registry_path(credential: AccessCredential, path: str) -> bool:
    if not isinstance(path, str) or not path:
        return False
    allowed_paths = visible_registry_request_paths(credential.grant.release, get_settings().artifact_path)
    if path in allowed_paths:
        return True

    release = credential.grant.release
    skill_version = release.skill_version
    skill = skill_version.skill
    namespace = skill.namespace
    return path.startswith(f'/registry/skills/{namespace.slug}/{skill.slug}/{skill_version.version}/')
