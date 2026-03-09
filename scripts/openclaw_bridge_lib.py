#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.DOTALL)


class OpenClawBridgeError(Exception):
    pass


def slugify(value: str) -> str:
    lowered = (value or '').strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', lowered)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def resolve_skill_dir(path_value: str) -> Path:
    candidate = Path(path_value).expanduser().resolve()
    if candidate.is_file() and candidate.name == 'SKILL.md':
        candidate = candidate.parent
    if not candidate.is_dir():
        raise OpenClawBridgeError(f'source path is not a skill directory: {candidate}')
    if not (candidate / 'SKILL.md').is_file():
        raise OpenClawBridgeError(f'missing SKILL.md in source directory: {candidate}')
    return candidate


def parse_skill_frontmatter(skill_md_path: Path) -> Dict[str, str]:
    content = skill_md_path.read_text(encoding='utf-8')
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise OpenClawBridgeError(f'missing YAML frontmatter in {skill_md_path}')

    fields = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, value = line.split(':', 1)
        fields[key.strip()] = _strip_quotes(value)

    if not fields.get('name'):
        raise OpenClawBridgeError(f'missing frontmatter name in {skill_md_path}')
    if not fields.get('description'):
        raise OpenClawBridgeError(f'missing frontmatter description in {skill_md_path}')
    return fields


def derive_registry_meta(frontmatter: Dict[str, str], owner: str, publisher: Optional[str] = None) -> Dict[str, object]:
    owner_value = (owner or '').strip()
    if not owner_value:
        raise OpenClawBridgeError('owner must be non-empty')

    slug = slugify(frontmatter.get('name', ''))
    if not slug:
        raise OpenClawBridgeError('frontmatter name does not produce a valid registry slug')

    publisher_slug = slugify(publisher) if publisher else ''
    meta = {
        'name': slug,
        'version': '0.1.0',
        'status': 'incubating',
        'summary': frontmatter.get('description', '').strip(),
        'owner': owner_value,
        'owners': [owner_value],
        'author': owner_value,
        'maintainers': [],
        'tags': [],
        'agent_compatible': ['openclaw', 'claude-code', 'codex'],
        'derived_from': None,
        'replaces': None,
        'visibility': 'private',
        'review_state': 'draft',
        'risk_level': 'low',
        'requires': {
            'tools': [],
            'bins': [],
            'env': [],
        },
        'entrypoints': {
            'skill_md': 'SKILL.md',
        },
        'tests': {
            'smoke': 'tests/smoke.md',
        },
        'distribution': {
            'installable': True,
            'channel': 'git',
        },
        'depends_on': [],
        'conflicts_with': [],
    }
    if publisher_slug:
        meta['publisher'] = publisher_slug
        meta['qualified_name'] = f'{publisher_slug}/{slug}'
    return meta


def scaffold_imported_skill(source_dir: Path, target_dir: Path, meta: Dict[str, object], force: bool = False) -> Dict[str, object]:
    if target_dir.exists():
        if not force:
            raise OpenClawBridgeError(f'target already exists: {target_dir}')
        shutil.rmtree(target_dir)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    (target_dir / '_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (target_dir / 'reviews.json').write_text(
        json.dumps({'version': 1, 'requests': [], 'entries': []}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    smoke_dir = target_dir / 'tests'
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / 'smoke.md').write_text(
        '# Smoke test\n\n'
        'Validate that the imported OpenClaw skill still matches its original intent and required files.\n',
        encoding='utf-8',
    )

    copied_files = []
    for path in sorted(target_dir.rglob('*')):
        if path.is_file():
            copied_files.append(str(path.relative_to(target_dir)))

    return {
        'target_dir': str(target_dir),
        'files': copied_files,
        'meta': meta,
    }


def load_ai_index(root: Path) -> Dict[str, object]:
    from ai_index_lib import validate_ai_index_payload

    index_path = root / 'catalog' / 'ai-index.json'
    if not index_path.exists():
        raise OpenClawBridgeError(f'missing AI index: {index_path}')
    payload = json.loads(index_path.read_text(encoding='utf-8'))
    errors = validate_ai_index_payload(payload)
    if errors:
        raise OpenClawBridgeError('; '.join(errors))
    return payload


def select_ai_skill(ai_index: Dict[str, object], requested: str) -> Dict[str, object]:
    matches = []
    for skill in ai_index.get('skills', []):
        if requested == skill.get('qualified_name') or requested == skill.get('name'):
            matches.append(skill)

    if not matches:
        raise OpenClawBridgeError(f'no AI-index entry found for {requested}')

    exact = [skill for skill in matches if requested == skill.get('qualified_name')]
    if exact:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    choices = ', '.join(sorted(skill.get('qualified_name') or skill.get('name') or '?' for skill in matches))
    raise OpenClawBridgeError(f'ambiguous skill name {requested}: {choices}')


def resolve_ai_release(root: Path, requested: str, requested_version: Optional[str] = None) -> Tuple[Dict[str, object], str, Dict[str, object]]:
    ai_index = load_ai_index(root)
    policy = ai_index.get('install_policy') or {}
    if policy.get('mode') != 'immutable-only' or policy.get('direct_source_install_allowed') is not False:
        raise OpenClawBridgeError('AI install policy must be immutable-only with direct source installs disabled')

    selected_skill = select_ai_skill(ai_index, requested)
    resolved_version = requested_version or selected_skill.get('default_install_version')
    versions = selected_skill.get('versions') or {}
    version_entry = versions.get(resolved_version)
    if not isinstance(version_entry, dict):
        raise OpenClawBridgeError(
            f'version {resolved_version!r} is not available for {selected_skill.get("qualified_name") or selected_skill.get("name")}'
        )
    if version_entry.get('installable') is not True:
        raise OpenClawBridgeError(f'version {resolved_version!r} is not installable')

    required_fields = ['manifest_path', 'bundle_path', 'bundle_sha256', 'attestation_path']
    missing = [field for field in required_fields if not isinstance(version_entry.get(field), str) or not version_entry.get(field).strip()]
    if missing:
        raise OpenClawBridgeError(f'missing distribution fields: {", ".join(missing)}')

    for field in ['manifest_path', 'bundle_path', 'attestation_path']:
        full_path = (root / version_entry[field]).resolve()
        if not full_path.exists():
            raise OpenClawBridgeError(f'missing {field}: {version_entry[field]}')

    return selected_skill, resolved_version, version_entry


def export_release_to_directory(root: Path, manifest_path: Path, export_dir: Path, force: bool = False) -> Dict[str, object]:
    from distribution_lib import materialize_distribution_source

    export_dir = export_dir.resolve()
    if export_dir.exists():
        if not force:
            raise OpenClawBridgeError(f'target already exists: {export_dir}')
        shutil.rmtree(export_dir)
    export_dir.parent.mkdir(parents=True, exist_ok=True)

    materialized = materialize_distribution_source(
        {
            'source_type': 'distribution-manifest',
            'distribution_manifest': str(manifest_path),
        },
        root=root,
    )
    source_dir = Path(materialized['materialized_path']).resolve()
    cleanup_dir = materialized.get('cleanup_dir')
    try:
        shutil.copytree(source_dir, export_dir)
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

    files = []
    for path in sorted(export_dir.rglob('*')):
        if path.is_file():
            files.append(str(path.relative_to(export_dir)))

    return {
        'export_dir': str(export_dir),
        'files': files,
    }
