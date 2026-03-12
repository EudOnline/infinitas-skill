#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

from canonical_skill_lib import load_skill_source

TOOL_INTENT_MAPPINGS = {
    'claude': {
        'plan_tracking': 'TodoWrite',
        'subagent_dispatch': 'Task',
        'shell_execution': 'Bash',
        'file_read': 'Read',
        'file_write': 'Write/Edit',
    },
    'codex': {
        'plan_tracking': 'update_plan',
        'subagent_dispatch': 'spawn_agent',
        'shell_execution': 'shell',
        'file_read': 'file tool',
        'file_write': 'file tool',
    },
    'openclaw': {
        'plan_tracking': 'agent-managed planning',
        'subagent_dispatch': 'not-native',
        'shell_execution': 'shell',
        'file_read': 'file access',
        'file_write': 'file access',
    },
}


class RenderSkillError(Exception):
    pass


def load_platform_profile(root: Path, platform: str) -> dict:
    profile_path = root / 'profiles' / f'{platform}.json'
    if not profile_path.is_file():
        raise RenderSkillError(f'missing platform profile: {profile_path}')
    try:
        payload = json.loads(profile_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RenderSkillError(f'invalid JSON in {profile_path}: {exc}') from exc
    if payload.get('platform') != platform:
        raise RenderSkillError(f'platform profile {profile_path} has mismatched platform {payload.get("platform")!r}')
    return payload


def apply_tool_intent_mapping(source: dict, platform: str, profile: dict) -> dict:
    mapping = dict(TOOL_INTENT_MAPPINGS.get(platform, {}))
    return {
        'profile_platform': profile.get('platform'),
        'required': {intent: mapping.get(intent, intent) for intent in source.get('tool_intents', {}).get('required', [])},
        'optional': {intent: mapping.get(intent, intent) for intent in source.get('tool_intents', {}).get('optional', [])},
    }


def render_skill_markdown(source: dict, platform: str, profile: dict) -> str:
    frontmatter = [
        '---',
        f"name: {source.get('name')}",
        f"description: {source.get('description')}",
    ]
    platform_overrides = source.get('platform_overrides', {}).get(platform, {}) if isinstance(source.get('platform_overrides'), dict) else {}
    if platform == 'openclaw':
        requires = platform_overrides.get('requires') or []
        if not requires:
            requires = [intent.replace('_', '-') for intent in source.get('tool_intents', {}).get('required', [])]
        rendered_requires = ', '.join(requires) if requires else 'none'
        frontmatter.append(f"metadata.openclaw.requires: {rendered_requires}")
        license_value = platform_overrides.get('license') or (source.get('distribution') or {}).get('license')
        if license_value:
            frontmatter.append(f"metadata.openclaw.license: {license_value}")
    frontmatter.append('---')
    body = Path(source['instructions_body_path']).read_text(encoding='utf-8').rstrip()
    mappings = apply_tool_intent_mapping(source, platform, profile)
    mapping_lines = []
    if mappings['required'] or mappings['optional']:
        mapping_lines.extend([
            '',
            '## Platform Tool Mapping',
        ])
        if mappings['required']:
            mapping_lines.append('')
            mapping_lines.append('Required intents:')
            for intent, mapped in mappings['required'].items():
                mapping_lines.append(f'- `{intent}` -> `{mapped}`')
        if mappings['optional']:
            mapping_lines.append('')
            mapping_lines.append('Optional intents:')
            for intent, mapped in mappings['optional'].items():
                mapping_lines.append(f'- `{intent}` -> `{mapped}`')
    return '\n'.join(frontmatter) + '\n\n' + body + ('\n' + '\n'.join(mapping_lines) if mapping_lines else '') + '\n'


def _copy_support_dir(source_dir: Path, target_dir: Path, name: str):
    src = source_dir / name
    if not src.exists():
        return []
    dest = target_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return [str(path.relative_to(target_dir)) for path in sorted(dest.rglob('*')) if path.is_file()]


def _copy_legacy_entries(source_dir: Path, target_dir: Path):
    files = []
    for entry in sorted(source_dir.iterdir()):
        if entry.name == 'SKILL.md':
            continue
        dest = target_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dest)
            files.extend(str(path.relative_to(target_dir)) for path in sorted(dest.rglob('*')) if path.is_file())
        else:
            shutil.copy2(entry, dest)
            files.append(str(dest.relative_to(target_dir)))
    return files


def render_skill(source: dict, platform: str, out_dir: Path, profile: dict) -> dict:
    out_dir = Path(out_dir).resolve()
    source_dir = Path(source['source_dir']).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    if source.get('source_mode') == 'legacy':
        files.extend(_copy_legacy_entries(source_dir, out_dir))
    else:
        for dirname in ['references', 'assets', 'scripts']:
            files.extend(_copy_support_dir(source_dir, out_dir, dirname))
    skill_md = render_skill_markdown(source, platform, profile)
    (out_dir / 'SKILL.md').write_text(skill_md, encoding='utf-8')
    files = ['SKILL.md'] + [item for item in files if item != 'SKILL.md']
    return {
        'platform': platform,
        'profile_version': (profile.get('contract') or {}).get('last_verified'),
        'out_dir': str(out_dir),
        'files': files,
    }


def render_skill_from_dir(root: Path, skill_dir: Path, platform: str, out_dir: Path) -> dict:
    source = load_skill_source(skill_dir)
    profile = load_platform_profile(root, platform)
    return render_skill(source=source, platform=platform, out_dir=out_dir, profile=profile)
