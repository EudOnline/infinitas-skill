#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from render_skill_lib import RenderSkillError, render_skill_from_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--platform', required=True, choices=['claude', 'codex', 'openclaw'])
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    try:
        payload = render_skill_from_dir(root=root, skill_dir=Path(args.skill_dir), platform=args.platform, out_dir=Path(args.out))
    except RenderSkillError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        raise SystemExit(1)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
