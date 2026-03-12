#!/usr/bin/env python3
import json
import re
from pathlib import Path

from schema_version_lib import validate_schema_version

NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.DOTALL)


class CanonicalSkillError(Exception):
    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__('; '.join(self.errors))


REQUIRED_CANONICAL_FIELDS = [
    'schema_version',
    'name',
    'summary',
    'description',
    'instructions_body',
    'tool_intents',
    'verification',
]


def is_canonical_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / 'skill.json').is_file()


def is_legacy_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / '_meta.json').is_file() and (path / 'SKILL.md').is_file()


def parse_skill_frontmatter(skill_md_path: Path) -> dict:
    content = skill_md_path.read_text(encoding='utf-8')
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise CanonicalSkillError(f'missing YAML frontmatter in {skill_md_path}')
    fields = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, value = line.split(':', 1)
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        fields[key.strip()] = cleaned
    return fields


def validate_canonical_payload(payload: dict) -> list[str]:
    errors = []
    _schema_version, schema_errors = validate_schema_version(payload)
    errors.extend(schema_errors)
    if not isinstance(payload, dict):
        return ['canonical skill payload must be an object']
    for field in REQUIRED_CANONICAL_FIELDS:
        if field not in payload:
            errors.append(f'missing required canonical field {field}')
    name = payload.get('name')
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append(f'invalid canonical name {name!r}')
    for key in ['summary', 'description', 'instructions_body']:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{key} must be a non-empty string')
    tool_intents = payload.get('tool_intents')
    if not isinstance(tool_intents, dict):
        errors.append('tool_intents must be an object')
    else:
        for key in ['required', 'optional']:
            value = tool_intents.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f'tool_intents.{key} must be an array of strings')
    verification = payload.get('verification')
    if not isinstance(verification, dict):
        errors.append('verification must be an object')
    else:
        required_platforms = verification.get('required_platforms')
        if not isinstance(required_platforms, list) or not all(isinstance(item, str) for item in required_platforms):
            errors.append('verification.required_platforms must be an array of strings')
        smoke_prompts = verification.get('smoke_prompts')
        if smoke_prompts is not None and (not isinstance(smoke_prompts, list) or not all(isinstance(item, str) for item in smoke_prompts)):
            errors.append('verification.smoke_prompts must be an array of strings when present')
    distribution = payload.get('distribution')
    if distribution is not None and not isinstance(distribution, dict):
        errors.append('distribution must be an object when present')
    degrades_to = payload.get('degrades_to')
    if degrades_to is not None and not isinstance(degrades_to, dict):
        errors.append('degrades_to must be an object when present')
    return errors


def _load_platform_overrides(skill_dir: Path) -> dict:
    overlays = {}
    platforms_dir = skill_dir / 'platforms'
    if not platforms_dir.is_dir():
        return overlays
    for path in sorted(platforms_dir.glob('*.json')):
        try:
            overlays[path.stem] = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise CanonicalSkillError(f'invalid JSON in {path}: {exc}') from exc
    return overlays


def load_canonical_skill(path: Path) -> dict:
    skill_dir = Path(path).resolve()
    payload_path = skill_dir / 'skill.json'
    if not payload_path.is_file():
        raise CanonicalSkillError(f'missing skill.json in canonical skill directory: {skill_dir}')
    try:
        payload = json.loads(payload_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise CanonicalSkillError(f'invalid JSON in {payload_path}: {exc}') from exc
    errors = validate_canonical_payload(payload)
    instructions_body_path = skill_dir / payload.get('instructions_body', '')
    if not instructions_body_path.is_file():
        errors.append(f'missing canonical instructions body: {payload.get("instructions_body")!r}')
    if errors:
        raise CanonicalSkillError(errors)
    return {
        'schema_version': payload.get('schema_version', 1),
        'name': payload.get('name'),
        'summary': payload.get('summary'),
        'description': payload.get('description'),
        'triggers': list(payload.get('triggers') or []),
        'examples': list(payload.get('examples') or []),
        'instructions_body_path': str(instructions_body_path),
        'tool_intents': {
            'required': list((payload.get('tool_intents') or {}).get('required') or []),
            'optional': list((payload.get('tool_intents') or {}).get('optional') or []),
        },
        'platform_overrides': _load_platform_overrides(skill_dir),
        'distribution': dict(payload.get('distribution') or {}),
        'verification': dict(payload.get('verification') or {}),
        'degrades_to': dict(payload.get('degrades_to') or {}),
        'source_mode': 'canonical',
        'source_dir': str(skill_dir),
        'payload_path': str(payload_path),
    }


def load_legacy_skill(path: Path) -> dict:
    skill_dir = Path(path).resolve()
    meta_path = skill_dir / '_meta.json'
    skill_md_path = skill_dir / 'SKILL.md'
    if not meta_path.is_file() or not skill_md_path.is_file():
        raise CanonicalSkillError(f'missing legacy skill files in {skill_dir}')
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise CanonicalSkillError(f'invalid JSON in {meta_path}: {exc}') from exc
    _schema_version, schema_errors = validate_schema_version(meta)
    if schema_errors:
        raise CanonicalSkillError(schema_errors)
    frontmatter = parse_skill_frontmatter(skill_md_path)
    name = meta.get('name')
    if not isinstance(name, str) or not name.strip():
        raise CanonicalSkillError('legacy skill metadata must define name')
    return {
        'schema_version': meta.get('schema_version', 1),
        'name': name,
        'summary': meta.get('summary') or '',
        'description': frontmatter.get('description') or '',
        'triggers': [],
        'examples': [],
        'instructions_body_path': str(skill_md_path),
        'tool_intents': {
            'required': [],
            'optional': [],
        },
        'platform_overrides': {},
        'distribution': dict(meta.get('distribution') or {}),
        'verification': {
            'required_platforms': list(meta.get('agent_compatible') or []),
            'smoke_prompts': [((meta.get('tests') or {}).get('smoke'))] if ((meta.get('tests') or {}).get('smoke')) else [],
        },
        'degrades_to': {},
        'source_mode': 'legacy',
        'source_dir': str(skill_dir),
        'payload_path': str(meta_path),
    }


def load_skill_source(path: Path) -> dict:
    candidate = Path(path).resolve()
    if is_canonical_skill_dir(candidate):
        return load_canonical_skill(candidate)
    if is_legacy_skill_dir(candidate):
        return load_legacy_skill(candidate)
    raise CanonicalSkillError(f'unsupported skill source layout: {candidate}')
