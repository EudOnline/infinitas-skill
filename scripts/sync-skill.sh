#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/sync-skill.sh <skill-name> [target-dir] [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
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
MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"

[[ -d "$SRC" ]] || { echo "missing active skill: $NAME" >&2; exit 1; }
[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null

readarray -t INFO < <(python3 - "$SRC/_meta.json" "$MANIFEST" "$NAME" <<'PY'
import json, sys
meta_path, manifest_path, name = sys.argv[1:4]
with open(meta_path, 'r', encoding='utf-8') as f:
    src = json.load(f)
print(src.get('version') or '')
locked = ''
installed = ''
if manifest_path and __import__('os').path.isfile(manifest_path):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    item = (manifest.get('skills') or {}).get(name) or {}
    locked = item.get('locked_version') or ''
    installed = item.get('version') or ''
print(locked)
print(installed)
PY
)
SRC_VERSION="${INFO[0]}"
LOCKED_VERSION="${INFO[1]}"
INSTALLED_VERSION="${INFO[2]}"

if [[ -n "$LOCKED_VERSION" && "$LOCKED_VERSION" != "$SRC_VERSION" ]]; then
  echo "installed skill is version-locked to $LOCKED_VERSION; active version is $SRC_VERSION" >&2
  echo "refusing to sync without updating the lock policy" >&2
  exit 1
fi

if [[ $FORCE -ne 1 ]]; then
  echo "source version: $SRC_VERSION"
  echo "installed version: $INSTALLED_VERSION"
fi

rm -rf "$DEST"
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" sync "${LOCKED_VERSION:-$SRC_VERSION}" >/dev/null
echo "synced: $DEST"
