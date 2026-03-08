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

BASE_DIR=""
for stage in active incubating archived; do
  if [[ -d "$ROOT/skills/$stage/$BASE_NAME" ]]; then
    BASE_DIR="$ROOT/skills/$stage/$BASE_NAME"
    break
  fi
done
[[ -n "$BASE_DIR" ]] || { echo "cannot resolve ancestor skill: $BASE_NAME" >&2; exit 1; }

ACTUAL_BASE_VERSION="$(python3 - "$BASE_DIR/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(meta.get('version') or '')
PY
)"

echo "ancestor: $BASE_DIR"
if [[ -n "$BASE_VERSION" && "$BASE_VERSION" != "$ACTUAL_BASE_VERSION" ]]; then
  echo "WARN: requested ancestor version $BASE_VERSION but resolved current version $ACTUAL_BASE_VERSION" >&2
fi

if [[ $NO_DIFF -eq 0 ]]; then
  echo
  diff -ru "$BASE_DIR" "$DIR" || true
fi
