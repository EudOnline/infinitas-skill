#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/install-skill.sh <skill-name> [target-dir] [--force]" >&2
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
mkdir -p "$TARGET_DIR"
if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "target already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi
cp -R "$SRC" "$DEST"
echo "installed: $DEST"
