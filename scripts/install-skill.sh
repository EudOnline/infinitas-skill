#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/install-skill.sh <skill-name> [target-dir] [--force] [--version X.Y.Z]" >&2
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
POSITIONAL=()

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

"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null
mkdir -p "$TARGET_DIR"
if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "target already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" install "${LOCK_VERSION:-$RESOLVED_VERSION}" >/dev/null
echo "installed: $DEST <- $SRC"
