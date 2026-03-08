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
DEST="$TARGET_DIR/$NAME"
MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"

[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }

readarray -t INFO < <(python3 - "$MANIFEST" "$NAME" <<'PY'
import json, os, sys
manifest_path, name = sys.argv[1:3]
item = {}
if os.path.isfile(manifest_path):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    item = (manifest.get('skills') or {}).get(name) or {}
print(item.get('locked_version') or '')
print(item.get('version') or '')
print(item.get('source_stage') or '')
print(item.get('source_registry') or '')
PY
)
LOCKED_VERSION="${INFO[0]}"
INSTALLED_VERSION="${INFO[1]}"
SOURCE_STAGE="${INFO[2]}"
MANIFEST_REGISTRY="${INFO[3]}"

ARGS=("$NAME" --json)
if [[ -n "$LOCKED_VERSION" ]]; then
  ARGS+=(--version "$LOCKED_VERSION")
fi
if [[ -n "$MANIFEST_REGISTRY" ]]; then
  ARGS+=(--registry "$MANIFEST_REGISTRY")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
SRC="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1])['path'])
PY
)"
SRC_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('version') or '')
PY
)"
SRC_STAGE="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('stage') or '')
PY
)"
SOURCE_REGISTRY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('registry_name') or 'self')
PY
)"

python3 - <<'PY' "$INFO_JSON"
import json, sys
info = json.loads(sys.argv[1])
commit = info.get('registry_commit') or ''
tag = info.get('registry_tag')
ref = info.get('registry_ref')
summary = f"resolved: {info.get('name')}@{info.get('version') or '?'} from {info.get('registry_name')}"
if commit:
    summary += f" @{commit[:12]}"
if tag:
    summary += f" tag={tag}"
elif ref:
    summary += f" ref={ref}"
print(summary)
PY

"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null
"$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" >/dev/null 2>&1 || { echo "sync target failed dependency/conflict checks" >&2; "$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR"; exit 1; }

if [[ -n "$LOCKED_VERSION" && "$LOCKED_VERSION" != "$SRC_VERSION" ]]; then
  echo "installed skill is version-locked to $LOCKED_VERSION; resolved source version is $SRC_VERSION" >&2
  echo "refusing to sync without updating the lock policy" >&2
  exit 1
fi

if [[ $FORCE -ne 1 ]]; then
  echo "source version: $SRC_VERSION ($SRC_STAGE)"
  echo "installed version: $INSTALLED_VERSION ($SOURCE_STAGE)"
  echo "source registry: $SOURCE_REGISTRY"
fi

rm -rf "$DEST"
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" sync "${LOCKED_VERSION:-$SRC_VERSION}" "$INFO_JSON" >/dev/null
echo "synced: $DEST <- $SRC"
