#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY' | while IFS= read -r name; do
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
cfg = json.loads((root / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))
for reg in cfg.get('registries', []):
    if reg.get('enabled', True):
        print(reg.get('name'))
PY
  [[ -n "$name" ]] || continue
  echo "syncing: $name"
  "$ROOT/scripts/sync-registry-source.sh" "$name"
done
