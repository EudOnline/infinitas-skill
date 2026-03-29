from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session, joinedload

from server.models import AccessCredential, AccessGrant, Exposure, Release, ReviewCase, User
from server.modules.access.authn import (
    extract_bearer_token,
    find_access_credential_by_token,
    find_user_by_token,
)
from server.modules.authoring.models import Namespace, Skill, SkillVersion
from server.modules.shared.enums import ExposureMode, ReviewRequirement
from server.settings import Settings, get_settings

INSTALL_POLICY = {
    'mode': 'immutable-only',
    'direct_source_install_allowed': False,
    'require_attestation': True,
    'require_sha256': True,
}
OPENCLAW_INTEROP = {
    'runtime_targets': ['~/.openclaw/skills', '~/.openclaw/workspace/skills'],
    'import_supported': True,
    'export_supported': True,
    'public_publish': {
        'clawhub': {
            'supported': True,
            'default': False,
        }
    },
}
TOP_LEVEL_METADATA_PATHS = frozenset(
    {
        '/registry/ai-index.json',
        '/registry/discovery-index.json',
        '/registry/distributions.json',
        '/registry/compatibility.json',
    }
)
SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$')


@dataclass(frozen=True)
class RegistryAudience:
    mode: str
    token: str | None
    user: User | None = None
    credential: AccessCredential | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _resolve_request_token(request: Request) -> str | None:
    return extract_bearer_token(request.headers.get('authorization')) or request.cookies.get('infinitas_auth_token')


def _semver_key(value: str | None) -> tuple[int, int, int, int, str]:
    if not isinstance(value, str):
        return (-1, -1, -1, -1, '')
    match = SEMVER_RE.match(value.strip())
    if not match:
        return (-1, -1, -1, -1, value)
    major, minor, patch, suffix = match.groups()
    stability = 1 if suffix is None else 0
    return (int(major), int(minor), int(patch), stability, suffix or '')


def _sort_versions(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if isinstance(value, str) and value not in unique:
            unique.append(value)
    return sorted(unique, key=_semver_key, reverse=True)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _static_payload(settings: Settings, name: str) -> dict:
    for path in (
        settings.artifact_path / name,
        settings.root_dir / 'catalog' / name,
    ):
        payload = _load_json(path)
        if payload:
            return payload
    return {}


def _manifest_payload(artifact_root: Path, manifest_ref: str | None) -> dict:
    if not isinstance(manifest_ref, str) or not manifest_ref.strip():
        return {}
    return _load_json(artifact_root / manifest_ref)


def _version_paths_from_manifest(manifest_ref: str | None, manifest_payload: dict) -> dict[str, str | None]:
    bundle = manifest_payload.get('bundle') if isinstance(manifest_payload.get('bundle'), dict) else {}
    attestation_bundle = (
        manifest_payload.get('attestation_bundle') if isinstance(manifest_payload.get('attestation_bundle'), dict) else {}
    )
    return {
        'manifest_path': manifest_ref,
        'bundle_path': bundle.get('path'),
        'bundle_sha256': bundle.get('sha256'),
        'attestation_path': attestation_bundle.get('provenance_path'),
        'attestation_signature_path': attestation_bundle.get('signature_path'),
        'published_at': manifest_payload.get('generated_at'),
    }


def _release_manifest_ref(release: Release) -> str | None:
    for artifact in release.artifacts:
        if artifact.kind == 'manifest' and isinstance(artifact.path, str) and artifact.path.strip():
            return artifact.path
    for artifact in release.artifacts:
        if isinstance(artifact.path, str) and artifact.path.endswith('manifest.json'):
            return artifact.path
    return None


def _distribution_entry_from_release(
    release: Release,
    *,
    artifact_root: Path,
) -> dict | None:
    manifest_ref = _release_manifest_ref(release)
    manifest_payload = _manifest_payload(artifact_root, manifest_ref)
    if not manifest_payload:
        return None

    skill_payload = manifest_payload.get('skill') if isinstance(manifest_payload.get('skill'), dict) else {}
    bundle = manifest_payload.get('bundle') if isinstance(manifest_payload.get('bundle'), dict) else {}
    attestation_bundle = (
        manifest_payload.get('attestation_bundle') if isinstance(manifest_payload.get('attestation_bundle'), dict) else {}
    )
    source_snapshot = manifest_payload.get('source_snapshot') if isinstance(manifest_payload.get('source_snapshot'), dict) else {}
    build = manifest_payload.get('build') if isinstance(manifest_payload.get('build'), dict) else {}
    file_manifest = manifest_payload.get('file_manifest') if isinstance(manifest_payload.get('file_manifest'), list) else []
    dependencies = manifest_payload.get('dependencies') if isinstance(manifest_payload.get('dependencies'), dict) else {}

    skill_version = release.skill_version
    skill = skill_version.skill
    namespace = skill.namespace
    publisher = skill_payload.get('publisher') or namespace.slug
    name = skill_payload.get('name') or skill.slug
    version = skill_payload.get('version') or skill_version.version
    qualified_name = skill_payload.get('qualified_name') or f'{publisher}/{name}'

    installed_integrity_capability = 'supported' if file_manifest else 'unknown'
    installed_integrity_reason = None if file_manifest else 'missing-signed-file-manifest'

    return {
        'name': name,
        'publisher': publisher,
        'qualified_name': qualified_name,
        'identity_mode': skill_payload.get('identity_mode') or 'qualified',
        'version': version,
        'status': skill_payload.get('status') or 'active',
        'summary': skill_payload.get('summary') or '',
        'manifest_path': manifest_ref,
        'bundle_path': bundle.get('path'),
        'bundle_sha256': bundle.get('sha256'),
        'bundle_size': bundle.get('size'),
        'bundle_file_count': bundle.get('file_count'),
        'bundle_root_dir': bundle.get('root_dir'),
        'attestation_path': attestation_bundle.get('provenance_path'),
        'attestation_signature_path': attestation_bundle.get('signature_path'),
        'attestation_sha256': attestation_bundle.get('provenance_sha256'),
        'attestation_signature_sha256': attestation_bundle.get('signature_sha256'),
        'signer_identity': attestation_bundle.get('signer_identity'),
        'namespace': attestation_bundle.get('namespace'),
        'allowed_signers': attestation_bundle.get('allowed_signers'),
        'file_manifest_count': len(file_manifest) or None,
        'build_archive_format': build.get('archive_format'),
        'installed_integrity_capability': installed_integrity_capability,
        'installed_integrity_reason': installed_integrity_reason,
        'source_snapshot_kind': source_snapshot.get('kind'),
        'source_snapshot_tag': source_snapshot.get('tag'),
        'source_snapshot_ref': source_snapshot.get('ref'),
        'source_snapshot_commit': source_snapshot.get('commit'),
        'registry': {
            'default_registry': 'self',
            'registries_consulted': ['self'],
        },
        'dependencies': dependencies or {
            'mode': 'install',
            'root': {
                'name': name,
                'publisher': publisher,
                'qualified_name': qualified_name,
                'version': version,
                'registry': 'self',
                'stage': 'active',
                'path': manifest_ref,
                'source_type': 'distribution-manifest',
                'distribution_manifest': manifest_ref,
                'source_snapshot_tag': source_snapshot.get('tag'),
                'source_snapshot_commit': source_snapshot.get('commit'),
            },
            'steps': [],
            'registries_consulted': ['self'],
        },
        'depends_on': skill_payload.get('depends_on', []),
        'conflicts_with': skill_payload.get('conflicts_with', []),
        'generated_at': manifest_payload.get('generated_at'),
        'source_type': 'distribution-manifest',
        'version_paths': _version_paths_from_manifest(manifest_ref, manifest_payload),
    }


def _static_skill_lookup(payload: dict) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for item in payload.get('skills') or []:
        if not isinstance(item, dict):
            continue
        key = item.get('qualified_name') or item.get('name')
        if isinstance(key, str) and key:
            lookup[key] = item
    return lookup


def resolve_registry_audience(request: Request, db: Session) -> RegistryAudience:
    token = _resolve_request_token(request)
    settings = get_settings()
    if not token:
        return RegistryAudience(mode='anonymous', token=None)
    if token in settings.registry_read_tokens:
        return RegistryAudience(mode='reader', token=token)
    user = find_user_by_token(token, db)
    if user is not None:
        return RegistryAudience(mode='user', token=token, user=user)
    credential = find_access_credential_by_token(token, db)
    if credential is not None:
        return RegistryAudience(mode='grant', token=token, credential=credential)
    return RegistryAudience(mode='anonymous', token=token)


def _public_exposure_visible(exposure: Exposure, review_cases: list[ReviewCase]) -> bool:
    if exposure.review_requirement != ReviewRequirement.BLOCKING.value:
        return True
    return any(case.status == 'approved' for case in review_cases)


def _release_visible_to_audience(
    release: Release,
    *,
    audience: RegistryAudience,
    exposures_by_release: dict[int, list[Exposure]],
    review_cases_by_exposure: dict[int, list[ReviewCase]],
    grants_by_release: dict[int, list[AccessGrant]],
) -> bool:
    exposures = exposures_by_release.get(release.id) or []
    if not exposures:
        return False
    if audience.mode in {'reader', 'user'}:
        return True
    if audience.mode == 'grant':
        credential = audience.credential
        if credential is None:
            return False
        return any(grant.id == credential.grant_id for grant in grants_by_release.get(release.id) or [])
    return any(
        exposure.mode == ExposureMode.PUBLIC.value
        and _public_exposure_visible(exposure, review_cases_by_exposure.get(exposure.id) or [])
        for exposure in exposures
    )


def _query_dynamic_releases(db: Session) -> tuple[list[Release], dict[int, list[Exposure]], dict[int, list[ReviewCase]], dict[int, list[AccessGrant]]]:
    releases = (
        db.query(Release)
        .options(
            joinedload(Release.artifacts),
            joinedload(Release.skill_version).joinedload(SkillVersion.skill).joinedload(Skill.namespace),
        )
        .all()
    )
    exposures = list(db.query(Exposure).all())
    review_cases = list(db.query(ReviewCase).all())
    grants = list(db.query(AccessGrant).all())

    exposures_by_release: dict[int, list[Exposure]] = {}
    for exposure in exposures:
        exposures_by_release.setdefault(exposure.release_id, []).append(exposure)

    review_cases_by_exposure: dict[int, list[ReviewCase]] = {}
    for review_case in review_cases:
        review_cases_by_exposure.setdefault(review_case.exposure_id, []).append(review_case)

    grants_by_release: dict[int, list[AccessGrant]] = {}
    for grant in grants:
        grants_by_release.setdefault(grant.release_id, []).append(grant)

    return releases, exposures_by_release, review_cases_by_exposure, grants_by_release


def _dynamic_distribution_entries(settings: Settings, db: Session, request: Request) -> list[dict] | None:
    audience = resolve_registry_audience(request, db)
    releases, exposures_by_release, review_cases_by_exposure, grants_by_release = _query_dynamic_releases(db)
    if not any(exposures_by_release.values()):
        return None

    entries: list[dict] = []
    for release in releases:
        if not _release_visible_to_audience(
            release,
            audience=audience,
            exposures_by_release=exposures_by_release,
            review_cases_by_exposure=review_cases_by_exposure,
            grants_by_release=grants_by_release,
        ):
            continue
        entry = _distribution_entry_from_release(release, artifact_root=settings.artifact_path)
        if entry is not None:
            entries.append(entry)
    return sorted(entries, key=lambda item: ((item.get('qualified_name') or item.get('name') or ''), tuple(-part for part in _semver_key(item.get('version'))[:4]), item.get('version') or ''))


def _skill_defaults(dynamic_entry: dict, *, static_ai: dict | None, static_discovery: dict | None) -> dict:
    merged = {}
    for source in [static_discovery or {}, static_ai or {}]:
        merged.update({key: value for key, value in source.items() if value not in (None, '')})
    merged.setdefault('publisher', dynamic_entry.get('publisher'))
    merged.setdefault('summary', dynamic_entry.get('summary') or '')
    merged.setdefault('tags', [])
    merged.setdefault('maturity', 'stable')
    merged.setdefault('quality_score', 0)
    merged.setdefault('capabilities', [])
    merged.setdefault('last_verified_at', None)
    merged.setdefault('use_when', [])
    merged.setdefault('avoid_when', [])
    merged.setdefault('runtime_assumptions', [])
    merged.setdefault('agent_compatible', [])
    merged.setdefault('verified_support', {})
    merged.setdefault('compatibility', {'declared_support': [], 'verified_support': {}})
    merged.setdefault('entrypoints', {'skill_md': 'SKILL.md'})
    merged.setdefault('requires', {'tools': [], 'env': []})
    merged.setdefault('interop', {'openclaw': dict(OPENCLAW_INTEROP)})
    return merged


def _build_ai_index_from_entries(settings: Settings, entries: list[dict]) -> dict:
    static_ai_lookup = _static_skill_lookup(_static_payload(settings, 'ai-index.json'))
    static_discovery_lookup = _static_skill_lookup(_static_payload(settings, 'discovery-index.json'))
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        key = entry.get('qualified_name') or entry.get('name')
        if isinstance(key, str) and key:
            grouped.setdefault(key, []).append(entry)

    skills: list[dict] = []
    for key in sorted(grouped):
        versions = _sort_versions([item.get('version') for item in grouped[key] if isinstance(item.get('version'), str)])
        if not versions:
            continue
        version_lookup = {item.get('version'): item for item in grouped[key]}
        latest_version = versions[0]
        latest_entry = version_lookup[latest_version]
        defaults = _skill_defaults(
            latest_entry,
            static_ai=static_ai_lookup.get(key),
            static_discovery=static_discovery_lookup.get(key),
        )
        version_map = {}
        for version in versions:
            item = version_lookup[version]
            version_map[version] = {
                'manifest_path': item.get('manifest_path'),
                'distribution_manifest_path': item.get('manifest_path'),
                'bundle_path': item.get('bundle_path'),
                'bundle_sha256': item.get('bundle_sha256'),
                'attestation_path': item.get('attestation_path'),
                'attestation_signature_path': item.get('attestation_signature_path'),
                'published_at': item.get('generated_at'),
                'stability': 'stable',
                'installable': True,
                'attestation_formats': list(
                    ((static_ai_lookup.get(key) or {}).get('versions', {}).get(version, {}).get('attestation_formats') or ['ssh'])
                ),
                'trust_state': 'verified' if item.get('attestation_signature_path') else 'attested',
                'resolution': {
                    'preferred_source': 'distribution-manifest',
                    'fallback_allowed': False,
                },
            }
        skills.append(
            {
                'name': latest_entry.get('name'),
                'publisher': defaults.get('publisher') or latest_entry.get('publisher'),
                'qualified_name': key,
                'summary': defaults.get('summary') or latest_entry.get('summary') or '',
                'tags': list(defaults.get('tags') or []),
                'maturity': defaults.get('maturity') or 'stable',
                'quality_score': int(defaults.get('quality_score') or 0),
                'capabilities': list(defaults.get('capabilities') or []),
                'last_verified_at': defaults.get('last_verified_at'),
                'use_when': list(defaults.get('use_when') or []),
                'avoid_when': list(defaults.get('avoid_when') or []),
                'runtime_assumptions': list(defaults.get('runtime_assumptions') or []),
                'agent_compatible': list(defaults.get('agent_compatible') or []),
                'compatibility': defaults.get('compatibility')
                or {
                    'declared_support': [],
                    'verified_support': {},
                },
                'verified_support': defaults.get('verified_support') or {},
                'trust_state': version_map[latest_version].get('trust_state') or 'unknown',
                'default_install_version': latest_version,
                'latest_version': latest_version,
                'available_versions': versions,
                'entrypoints': defaults.get('entrypoints') or {'skill_md': 'SKILL.md'},
                'requires': defaults.get('requires') or {'tools': [], 'env': []},
                'interop': defaults.get('interop') or {'openclaw': dict(OPENCLAW_INTEROP)},
                'versions': version_map,
            }
        )

    return {
        'schema_version': 1,
        'generated_at': _utc_now_iso(),
        'registry': {
            'default_registry': 'self',
        },
        'install_policy': dict(INSTALL_POLICY),
        'skills': skills,
    }


def build_registry_ai_index_payload(settings: Settings, db: Session, request: Request) -> dict:
    entries = _dynamic_distribution_entries(settings, db, request)
    if entries is None:
        return _static_payload(settings, 'ai-index.json')
    return _build_ai_index_from_entries(settings, entries)


def build_registry_distributions_payload(settings: Settings, db: Session, request: Request) -> dict:
    entries = _dynamic_distribution_entries(settings, db, request)
    if entries is None:
        return _static_payload(settings, 'distributions.json')
    return {
        'generated_at': _utc_now_iso(),
        'skills': entries,
    }


def build_registry_discovery_payload(settings: Settings, db: Session, request: Request) -> dict:
    entries = _dynamic_distribution_entries(settings, db, request)
    if entries is None:
        return _static_payload(settings, 'discovery-index.json')
    ai_payload = _build_ai_index_from_entries(settings, entries)
    discovery_lookup = _static_skill_lookup(_static_payload(settings, 'discovery-index.json'))
    skills = []
    for skill in ai_payload.get('skills') or []:
        if not isinstance(skill, dict):
            continue
        qualified_name = skill.get('qualified_name') or skill.get('name')
        defaults = discovery_lookup.get(qualified_name, {})
        name = skill.get('name')
        publisher = skill.get('publisher')
        match_names = []
        for candidate in [name, qualified_name, f'{publisher}/{name}' if publisher and name else None]:
            if isinstance(candidate, str) and candidate and candidate not in match_names:
                match_names.append(candidate)
        skills.append(
            {
                'name': name,
                'qualified_name': qualified_name,
                'publisher': publisher,
                'summary': skill.get('summary') or '',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': sorted(match_names),
                'default_install_version': skill.get('default_install_version'),
                'latest_version': skill.get('latest_version'),
                'available_versions': list(skill.get('available_versions') or []),
                'agent_compatible': list(skill.get('agent_compatible') or []),
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': skill.get('trust_state') or 'unknown',
                'tags': list(skill.get('tags') or defaults.get('tags') or []),
                'maturity': defaults.get('maturity') or skill.get('maturity') or 'stable',
                'quality_score': int(defaults.get('quality_score') or skill.get('quality_score') or 0),
                'last_verified_at': skill.get('last_verified_at'),
                'capabilities': list(skill.get('capabilities') or []),
                'verified_support': skill.get('verified_support') or {},
                'attestation_formats': list(
                    ((skill.get('versions') or {}).get(skill.get('latest_version') or '', {}) or {}).get('attestation_formats')
                    or ['ssh']
                ),
                'use_when': list(skill.get('use_when') or []),
                'avoid_when': list(skill.get('avoid_when') or []),
                'runtime_assumptions': list(skill.get('runtime_assumptions') or []),
            }
        )
    return {
        'schema_version': 1,
        'generated_at': _utc_now_iso(),
        'default_registry': 'self',
        'sources': [
            {
                'name': 'self',
                'kind': 'http',
                'priority': 100,
                'trust_level': 'private',
                'root': '.',
                'status': 'ready',
                'base_url': None,
            }
        ],
        'resolution_policy': {
            'private_registry_first': True,
            'external_requires_confirmation': True,
            'auto_install_mutable_sources': False,
        },
        'skills': skills,
    }


def build_registry_compatibility_payload(settings: Settings, db: Session, request: Request) -> dict:
    entries = _dynamic_distribution_entries(settings, db, request)
    if entries is None:
        return _static_payload(settings, 'compatibility.json')
    payload = _static_payload(settings, 'compatibility.json')
    visible_keys = {
        (item.get('qualified_name') or item.get('name'), item.get('version'))
        for item in entries
        if isinstance(item.get('version'), str)
    }
    filtered = []
    for item in payload.get('skills') or []:
        if not isinstance(item, dict):
            continue
        key = (item.get('qualified_name') or item.get('name'), item.get('version'))
        if key in visible_keys:
            filtered.append(item)
    return {
        'generated_at': _utc_now_iso(),
        'skills': filtered,
    }


def load_search_skill_entries(settings: Settings, db: Session, request: Request) -> list[dict]:
    entries = _dynamic_distribution_entries(settings, db, request)
    if entries is None:
        payload = _static_payload(settings, 'catalog.json')
        return list(payload.get('skills') or [])
    return [
        {
            'id': item.get('qualified_name') or item.get('name'),
            'name': item.get('name'),
            'qualified_name': item.get('qualified_name') or item.get('name'),
            'version': item.get('version'),
            'latest_version': item.get('version'),
            'summary': item.get('summary') or '',
            'tags': [],
            'author': item.get('publisher'),
            'publisher': item.get('publisher'),
            'status': item.get('status') or 'active',
        }
        for item in entries
    ]


def visible_registry_request_paths(release: Release, artifact_root: Path) -> set[str]:
    manifest_ref = _release_manifest_ref(release)
    manifest_payload = _manifest_payload(artifact_root, manifest_ref)
    relative_paths = {
        artifact.path
        for artifact in release.artifacts
        if isinstance(artifact.path, str) and artifact.path.strip()
    }
    version_paths = _version_paths_from_manifest(manifest_ref, manifest_payload)
    for value in version_paths.values():
        if isinstance(value, str) and value.strip():
            relative_paths.add(value)

    request_paths: set[str] = set(TOP_LEVEL_METADATA_PATHS)
    skill_version = release.skill_version
    skill = skill_version.skill
    namespace = skill.namespace
    for rel_path in relative_paths:
        request_paths.add(f'/registry/{rel_path}')
        if rel_path.startswith('catalog/distributions/'):
            suffix = rel_path.removeprefix(f'catalog/distributions/{namespace.slug}/{skill.slug}/{skill_version.version}/')
            if suffix != rel_path:
                request_paths.add(f'/registry/skills/{namespace.slug}/{skill.slug}/{skill_version.version}/{suffix}')
        if rel_path.startswith('catalog/provenance/'):
            filename = rel_path.removeprefix('catalog/provenance/')
            request_paths.add(f'/registry/provenance/{filename}')
    return request_paths
