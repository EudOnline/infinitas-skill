#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/sync-skill.sh <skill-name> [target-dir] [--force]" >&2
  exit 1
fi

NAME="${1:-}"
shift || true
TARGET_DIR="$HOME/.openclaw/skills"
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *) TARGET_DIR="$arg" ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/active/$NAME"
DEST="$TARGET_DIR/$NAME"

[[ -d "$SRC" ]] || { echo "missing active skill: $NAME" >&2; exit 1; }
[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null

if [[ $FORCE -ne 1 ]]; then
  python3 - "$SRC" "$DEST" <<'PY'
import json, os, sys
src, dest = sys.argv[1:3]
def read_version(path):
    with open(os.path.join(path, '_meta.json'), 'r', encoding='utf-8') as f:
        return json.load(f).get('version')
print(f'source version: {read_version(src)}')
print(f'installed version: {read_version(dest)}')
PY
fi

rm -rf "$DEST"
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" sync >/dev/null
echo "synced: $DEST"
