#!/usr/bin/env python3
from install_manifest_lib import InstallManifestError, load_install_manifest


class InstalledSkillError(Exception):
    pass


def load_installed_skill(target_dir, requested_name):
    try:
        manifest = load_install_manifest(target_dir)
    except InstallManifestError as exc:
        raise InstalledSkillError(str(exc)) from exc

    skills = manifest.get('skills') or {}
    item = skills.get(requested_name)
    if not isinstance(item, dict):
        for candidate in skills.values():
            if not isinstance(candidate, dict):
                continue
            if candidate.get('qualified_name') == requested_name or candidate.get('name') == requested_name:
                item = candidate
                break

    if not isinstance(item, dict):
        raise InstalledSkillError(f'installed skill not found: {requested_name}')
    return manifest, item
