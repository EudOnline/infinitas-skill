#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if len(sys.argv) != 3:
    print('usage: scripts/check-install-target.py <skill-dir> <target-dir>', file=sys.stderr)
    raise SystemExit(1)

skill_dir = Path(sys.argv[1]).resolve()
target_dir = Path(sys.argv[2]).resolve()
meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
installed = {}
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    installed = manifest.get('skills') or {}
else:
    for child in sorted(p for p in target_dir.iterdir() if p.is_dir() and (p / '_meta.json').exists()) if target_dir.exists() else []:
        installed[child.name] = json.loads((child / '_meta.json').read_text(encoding='utf-8'))

errors = 0
for ref in meta.get('depends_on', []) or []:
    name, _, version = ref.partition('@')
    item = installed.get(name)
    if not item:
        print(f'FAIL: missing dependency in target: {ref}', file=sys.stderr)
        errors += 1
        continue
    if version and (item.get('locked_version') or item.get('version')) != version and item.get('version') != version:
        print(f'FAIL: dependency version mismatch for {ref}: installed {item.get("version")}', file=sys.stderr)
        errors += 1

for ref in meta.get('conflicts_with', []) or []:
    name, _, version = ref.partition('@')
    item = installed.get(name)
    if not item:
        continue
    if not version or item.get('version') == version or item.get('locked_version') == version:
        print(f'FAIL: conflicting installed skill present: {ref}', file=sys.stderr)
        errors += 1

if errors:
    raise SystemExit(1)
print(f'OK: install target check passed for {meta.get("name")}')
