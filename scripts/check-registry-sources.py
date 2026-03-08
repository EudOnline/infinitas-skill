#!/usr/bin/env python3
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / 'config' / 'registry-sources.json'
try:
    cfg = json.loads(path.read_text(encoding='utf-8'))
except Exception as e:
    print(f'FAIL: invalid registry-sources.json: {e}', file=sys.stderr)
    raise SystemExit(1)

errors = 0
registries = cfg.get('registries')
if not isinstance(registries, list) or not registries:
    print('FAIL: registries must be a non-empty array', file=sys.stderr)
    errors += 1
seen = set()
for reg in registries or []:
    if not isinstance(reg, dict):
        print('FAIL: each registry entry must be an object', file=sys.stderr)
        errors += 1
        continue
    name = reg.get('name')
    if not isinstance(name, str) or not name:
        print('FAIL: registry name must be a non-empty string', file=sys.stderr)
        errors += 1
    elif name in seen:
        print(f'FAIL: duplicate registry name: {name}', file=sys.stderr)
        errors += 1
    else:
        seen.add(name)
    kind = reg.get('kind')
    if kind not in {'git', 'local'}:
        print(f'FAIL: registry {name!r} kind must be git or local', file=sys.stderr)
        errors += 1
    if not isinstance(reg.get('trust'), str) or not reg.get('trust'):
        print(f'FAIL: registry {name!r} missing non-empty trust', file=sys.stderr)
        errors += 1
    if kind == 'git' and (not isinstance(reg.get('url'), str) or not reg.get('url')):
        print(f'FAIL: git registry {name!r} missing non-empty url', file=sys.stderr)
        errors += 1
    if kind == 'local' and (not isinstance(reg.get('local_path'), str) or not reg.get('local_path')):
        print(f'FAIL: local registry {name!r} missing non-empty local_path', file=sys.stderr)
        errors += 1
    if 'enabled' in reg and not isinstance(reg.get('enabled'), bool):
        print(f'FAIL: registry {name!r} enabled must be boolean', file=sys.stderr)
        errors += 1
    if 'priority' in reg and not isinstance(reg.get('priority'), int):
        print(f'FAIL: registry {name!r} priority must be integer', file=sys.stderr)
        errors += 1

if cfg.get('default_registry') not in seen:
    print('FAIL: default_registry must match one configured registry name', file=sys.stderr)
    errors += 1

if errors:
    raise SystemExit(1)
print(f'OK: validated {len(registries)} registry source(s)')
