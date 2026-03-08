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
SRC="$ROOT/skills/active/$NAME"
DEST="$TARGET_DIR/$NAME"

[[ -d "$SRC" ]] || { echo "missing active skill: $NAME" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null

ACTUAL_VERSION="$(python3 - "$SRC/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print(json.load(f).get('version') or '')
PY
)"

if [[ -n "$LOCK_VERSION" && "$LOCK_VERSION" != "$ACTUAL_VERSION" ]]; then
  echo "requested version $LOCK_VERSION but active skill is at $ACTUAL_VERSION" >&2
  echo "Use archived snapshots for exact historical installs." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "target already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" install "${LOCK_VERSION:-$ACTUAL_VERSION}" >/dev/null
echo "installed: $DEST"
