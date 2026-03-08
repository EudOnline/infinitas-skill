#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/lineage-diff.sh <skill-name-or-path> [--no-diff]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
NO_DIFF=0
for arg in "$@"; do
  [[ "$arg" == "--no-diff" ]] && NO_DIFF=1
done

resolve_skill() {
  local name="$1"
  if [[ -d "$name" && -f "$name/_meta.json" ]]; then
    printf '%s' "$name"
    return
  fi
  for stage in active incubating archived; do
    if [[ -d "$ROOT/skills/$stage/$name" ]]; then
      printf '%s' "$ROOT/skills/$stage/$name"
      return
    fi
  done
  return 1
}

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
DERIVED_FROM="$(python3 - "$DIR/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(meta.get('derived_from') or '')
PY
)"

python3 - "$DIR/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(f"skill: {meta.get('name')}@{meta.get('version')} ({meta.get('status')})")
print(f"derived_from: {meta.get('derived_from')}")
PY

if [[ -z "$DERIVED_FROM" ]]; then
  echo "No derived_from metadata set."
  exit 0
fi

BASE_NAME="${DERIVED_FROM%@*}"
BASE_VERSION="${DERIVED_FROM#*@}"
if [[ "$BASE_NAME" == "$BASE_VERSION" ]]; then
  BASE_VERSION=""
fi

BASE_DIR="$(python3 - "$ROOT" "$BASE_NAME" "$BASE_VERSION" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
base_name = sys.argv[2]
base_version = sys.argv[3]

candidates = []
for stage in ['active', 'incubating', 'archived']:
    stage_dir = root / 'skills' / stage
    if not stage_dir.exists():
        continue
    for d in sorted(p for p in stage_dir.iterdir() if p.is_dir() and (p / '_meta.json').exists()):
        with open(d / '_meta.json', 'r', encoding='utf-8') as f:
            meta = json.load(f)
        candidates.append((stage, d, meta))

if base_version:
    exact = []
    for stage, d, meta in candidates:
        name = meta.get('name')
        version = meta.get('version')
        snapshot_of = meta.get('snapshot_of')
        if name == base_name and version == base_version:
            exact.append((stage, d, meta))
        elif snapshot_of == f'{base_name}@{base_version}':
            exact.append((stage, d, meta))
    # prefer archived exact snapshot, then active/incubating exact version
    def key(item):
        stage, d, meta = item
        order = {'archived': 0, 'active': 1, 'incubating': 2}.get(stage, 9)
        return (order, str(d))
    exact.sort(key=key)
    if exact:
        print(exact[0][1])
        raise SystemExit(0)

for stage in ['active', 'incubating', 'archived']:
    d = root / 'skills' / stage / base_name
    if d.is_dir() and (d / '_meta.json').exists():
        print(d)
        raise SystemExit(0)

raise SystemExit(1)
PY
)" || { echo "cannot resolve ancestor skill: $BASE_NAME${BASE_VERSION:+@$BASE_VERSION}" >&2; exit 1; }

ACTUAL_BASE_VERSION="$(python3 - "$BASE_DIR/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(meta.get('version') or '')
PY
)"

echo "ancestor: $BASE_DIR"
if [[ -n "$BASE_VERSION" && "$BASE_VERSION" != "$ACTUAL_BASE_VERSION" ]]; then
  SNAPSHOT_OF="$(python3 - "$BASE_DIR/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(meta.get('snapshot_of') or '')
PY
)"
  if [[ "$SNAPSHOT_OF" != "$BASE_NAME@$BASE_VERSION" ]]; then
    echo "WARN: requested ancestor version $BASE_VERSION but resolved current version $ACTUAL_BASE_VERSION" >&2
  fi
fi

if [[ $NO_DIFF -eq 0 ]]; then
  echo
  diff -ru "$BASE_DIR" "$DIR" || true
fi
