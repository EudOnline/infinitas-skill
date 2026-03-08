#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/install-skill.sh <skill-name> [target-dir] [--force] [--version X.Y.Z] [--registry NAME] [--no-deps]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

NAME="$1"
shift || true
TARGET_DIR="$HOME/.openclaw/skills"
FORCE=0
LOCK_VERSION=""
REGISTRY=""
AUTO_DEPS=1
POSITIONAL=()
STACK=",${INFINITAS_SKILL_INSTALL_STACK:-},"
if [[ "$STACK" == *",$NAME,"* ]]; then
  echo "detected dependency cycle while installing $NAME" >&2
  exit 1
fi
export INFINITAS_SKILL_INSTALL_STACK="${INFINITAS_SKILL_INSTALL_STACK:+$INFINITAS_SKILL_INSTALL_STACK,}$NAME"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --version)
      LOCK_VERSION="${2:-}"
      [[ -n "$LOCK_VERSION" ]] || { echo "missing value for --version" >&2; exit 1; }
      shift 2
      ;;
    --registry)
      REGISTRY="${2:-}"
      [[ -n "$REGISTRY" ]] || { echo "missing value for --registry" >&2; exit 1; }
      shift 2
      ;;
    --no-deps)
      AUTO_DEPS=0
      shift
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if [[ ${#POSITIONAL[@]} -gt 1 ]]; then
  usage
  exit 1
fi
if [[ ${#POSITIONAL[@]} -eq 1 ]]; then
  TARGET_DIR="${POSITIONAL[0]}"
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$TARGET_DIR/$NAME"
ARGS=("$NAME" --json)
if [[ -n "$LOCK_VERSION" ]]; then
  ARGS+=(--version "$LOCK_VERSION")
fi
if [[ -n "$REGISTRY" ]]; then
  ARGS+=(--registry "$REGISTRY")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
SRC="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1])['path'])
PY
)"
RESOLVED_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('version') or '')
PY
)"
RESOLVED_REGISTRY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('registry_name') or 'self')
PY
)"

"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null
mkdir -p "$TARGET_DIR"

if [[ $AUTO_DEPS -eq 1 ]]; then
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    DEP_NAME="${ref%@*}"
    DEP_VERSION=""
    if [[ "$ref" == *"@"* ]]; then
      DEP_VERSION="${ref#*@}"
    fi
    if python3 - "$TARGET_DIR" "$DEP_NAME" "$DEP_VERSION" <<'PY'
import json, sys
from pathlib import Path
target, dep_name, dep_version = sys.argv[1:4]
manifest = Path(target) / '.infinitas-skill-install-manifest.json'
installed = {}
if manifest.exists():
    installed = json.loads(manifest.read_text(encoding='utf-8')).get('skills', {}) or {}
item = installed.get(dep_name)
if not item:
    raise SystemExit(1)
if dep_version and item.get('version') != dep_version and item.get('locked_version') != dep_version:
    raise SystemExit(1)
PY
    then
      continue
    fi
    CMD=("$0" "$DEP_NAME" "$TARGET_DIR")
    [[ -n "$DEP_VERSION" ]] && CMD+=(--version "$DEP_VERSION")
    CMD+=(--registry "$RESOLVED_REGISTRY")
    [[ $FORCE -eq 1 ]] && CMD+=(--force)
    "${CMD[@]}"
  done < <(python3 - "$SRC/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
for ref in meta.get('depends_on', []) or []:
    print(ref)
PY
)
fi

"$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" >/dev/null 2>&1 || { echo "install target failed dependency/conflict checks" >&2; "$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR"; exit 1; }
if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "target already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" install "${LOCK_VERSION:-$RESOLVED_VERSION}" "$RESOLVED_REGISTRY" >/dev/null
echo "installed: $DEST <- $SRC"
