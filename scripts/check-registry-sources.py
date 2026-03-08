#!/usr/bin/env python3
import sys
from pathlib import Path

from registry_source_lib import load_registry_config, validate_registry_config

root = Path(__file__).resolve().parent.parent
try:
    cfg = load_registry_config(root)
except Exception as e:
    print(f'FAIL: invalid registry-sources.json: {e}', file=sys.stderr)
    raise SystemExit(1)

errors = validate_registry_config(root, cfg)
for error in errors:
    print(f'FAIL: {error}', file=sys.stderr)

if errors:
    raise SystemExit(1)
registries = cfg.get('registries', [])
print(f'OK: validated {len(registries)} registry source(s)')
