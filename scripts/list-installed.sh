#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-$HOME/.openclaw/skills}"
MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"

[[ -f "$MANIFEST" ]] || { echo "missing manifest: $MANIFEST" >&2; exit 1; }
python3 - "$MANIFEST" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"repo: {data.get('repo')}")
print(f"updated_at: {data.get('updated_at')}")
for name, meta in sorted(data.get('skills', {}).items()):
    version = meta.get('version')
    locked = meta.get('locked_version')
    stage = meta.get('source_stage')
    src = meta.get('source_path')
    history_len = len((data.get('history') or {}).get(name) or [])
    lock_note = f", locked={locked}" if locked else ""
    hist_note = f", history={history_len}" if history_len else ""
    print(f"- {name}: {version}{lock_note} [{stage}] ({meta.get('action')}) -> {meta.get('target_path')} from {src}{hist_note}")
PY
