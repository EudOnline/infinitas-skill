#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
cfg = json.loads((root / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))
print(f"default_registry: {cfg.get('default_registry')}")
for reg in cfg.get('registries', []):
    status = 'enabled' if reg.get('enabled', True) else 'disabled'
    print(f"- {reg.get('name')}: {reg.get('kind')} {reg.get('url')} [{status}, priority={reg.get('priority')}, trust={reg.get('trust')}]" )
