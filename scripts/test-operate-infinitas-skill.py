#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = 'operate-infinitas-skill'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'could not load JSON {path}: {exc}')


def assert_contains(text: str, needle: str, label: str):
    if needle not in text:
        fail(f'missing {label}: expected to find {needle!r}')


def resolve_skill_dir():
    candidates = [
        ROOT / 'skills' / 'incubating' / SKILL_NAME,
        ROOT / 'skills' / 'active' / SKILL_NAME,
    ]
    matches = [path for path in candidates if path.is_dir()]
    if not matches:
        fail(f'missing skill directory: expected one of {", ".join(str(path) for path in candidates)}')
    if len(matches) > 1:
        fail(f'expected exactly one lifecycle directory for {SKILL_NAME}, found {matches!r}')
    return matches[0]


def main():
    skill_dir = resolve_skill_dir()
    skill_md_path = skill_dir / 'SKILL.md'
    meta_path = skill_dir / '_meta.json'
    smoke_path = skill_dir / 'tests' / 'smoke.md'

    if not skill_md_path.is_file():
        fail(f'missing SKILL.md: {skill_md_path}')
    if not meta_path.is_file():
        fail(f'missing _meta.json: {meta_path}')
    if not smoke_path.is_file():
        fail(f'missing smoke test: {smoke_path}')

    skill_md = skill_md_path.read_text(encoding='utf-8')
    meta = load_json(meta_path)

    if 'description: Use when' not in skill_md:
        fail('expected trigger-focused SKILL.md description')

    for section in ['## Shared Model', '## OpenClaw', '## Codex', '## Claude Code']:
        assert_contains(skill_md, section, f'{section} section')

    for token in ['OpenClaw', 'Codex', 'Claude Code']:
        assert_contains(skill_md, token, f'{token} trigger coverage')

    for command in [
        'scripts/import-openclaw-skill.sh',
        'scripts/publish-skill.sh',
        'scripts/pull-skill.sh',
        'scripts/export-openclaw-skill.sh',
    ]:
        assert_contains(skill_md, command, f'{command} command guidance')

    if meta.get('name') != 'operate-infinitas-skill':
        fail(f"expected name 'operate-infinitas-skill', got {meta.get('name')!r}")
    if meta.get('publisher') != 'lvxiaoer':
        fail(f"expected publisher 'lvxiaoer', got {meta.get('publisher')!r}")
    if meta.get('qualified_name') != 'lvxiaoer/operate-infinitas-skill':
        fail(f"unexpected qualified_name: {meta.get('qualified_name')!r}")

    agents = meta.get('agent_compatible') or []
    for agent in ['openclaw', 'codex', 'claude', 'claude-code']:
        if agent not in agents:
            fail(f'missing agent compatibility for {agent!r}: {agents!r}')

    smoke = smoke_path.read_text(encoding='utf-8')
    assert_contains(smoke, 'publish-skill.sh', 'smoke publish guidance')
    assert_contains(smoke, 'pull-skill.sh', 'smoke pull guidance')

    print('OK: operate-infinitas-skill checks passed')


if __name__ == '__main__':
    main()
