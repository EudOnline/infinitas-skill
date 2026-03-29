from __future__ import annotations

import re

from server.models import AccessCredential


SKILL_ARTIFACT_PATH = re.compile(r'^/registry/skills/(?P<publisher>[^/]+)/(?P<skill>[^/]+)/(?P<version>[^/]+)/[^/]+$')


def credential_can_read_registry_path(credential: AccessCredential, path: str) -> bool:
    match = SKILL_ARTIFACT_PATH.match(path)
    if match is None:
        return False

    release = credential.grant.release
    skill_version = release.skill_version
    skill = skill_version.skill
    namespace = skill.namespace
    return (
        match.group('publisher') == namespace.slug
        and match.group('skill') == skill.slug
        and match.group('version') == skill_version.version
    )
