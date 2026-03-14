#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.artifact_ops import sync_catalog_artifacts


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-hosted-artifact-layout-'))
    try:
        artifact_root = tmpdir / 'artifacts'
        sync_catalog_artifacts(ROOT, artifact_root)

        required_paths = [
            artifact_root / 'ai-index.json',
            artifact_root / 'distributions.json',
            artifact_root / 'compatibility.json',
            artifact_root / 'catalog' / 'ai-index.json',
            artifact_root / 'skills' / 'lvxiaoer' / 'operate-infinitas-skill' / '0.1.1' / 'manifest.json',
            artifact_root / 'skills' / 'lvxiaoer' / 'operate-infinitas-skill' / '0.1.1' / 'skill.tar.gz',
            artifact_root / 'provenance' / 'operate-infinitas-skill-0.1.1.json',
            artifact_root / 'provenance' / 'operate-infinitas-skill-0.1.1.json.ssig',
        ]
        for path in required_paths:
            if not path.exists():
                fail(f'missing hosted artifact surface file: {path}')

        ai_index = json.loads((artifact_root / 'ai-index.json').read_text(encoding='utf-8'))
        skill_names = {item.get('qualified_name') for item in (ai_index.get('skills') or [])}
        if 'lvxiaoer/operate-infinitas-skill' not in skill_names:
            fail(f'expected operate-infinitas-skill in hosted ai-index, got {sorted(skill_names)!r}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print('OK: hosted artifact layout checks passed')


if __name__ == '__main__':
    main()
