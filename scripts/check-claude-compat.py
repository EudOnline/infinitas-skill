#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from canonical_skill_lib import parse_skill_frontmatter  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    errors = []
    skill_md = skill_dir / 'SKILL.md'
    if not skill_md.is_file():
        errors.append(f'missing SKILL.md: {skill_md}')
    else:
        try:
            frontmatter = parse_skill_frontmatter(skill_md)
        except Exception as exc:
            errors.append(str(exc))
            frontmatter = {}
        if not frontmatter.get('name'):
            errors.append('missing Claude frontmatter name')
        if not frontmatter.get('description'):
            errors.append('missing Claude frontmatter description')
        text = skill_md.read_text(encoding='utf-8')
        if '{{' in text or '__TOOL_INTENT__' in text:
            errors.append('unresolved tool-intent placeholders remain in SKILL.md')
    commands_dir = skill_dir / 'commands'
    if commands_dir.exists() and not any(commands_dir.glob('*.md')):
        errors.append('commands directory exists but has no markdown wrappers')
    payload = {'ok': not errors, 'platform': 'claude', 'skill_dir': str(skill_dir), 'errors': errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if errors:
            print('\n'.join(errors), file=sys.stderr)
        else:
            print(f'OK: {skill_dir}')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
