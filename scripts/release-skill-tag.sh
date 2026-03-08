#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/release-skill-tag.sh <skill-name-or-path> [--version X.Y.Z] [--create] [--force]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
CREATE=0
FORCE=0
SET_VERSION=""

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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      SET_VERSION="${2:-}"
      shift 2
      ;;
    --create)
      CREATE=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
readarray -t META < <(python3 - "$DIR/_meta.json" "$SET_VERSION" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
name = meta['name']
version = sys.argv[2] or meta['version']
status = meta.get('status')
print(name)
print(version)
print(status)
PY
)
NAME="${META[0]}"
VERSION="${META[1]}"
STATUS="${META[2]}"
TAG="skill/$NAME/v$VERSION"

echo "skill: $NAME"
echo "version: $VERSION"
echo "status: $STATUS"
echo "tag: $TAG"

if [[ $CREATE -eq 1 ]]; then
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    if [[ $FORCE -ne 1 ]]; then
      echo "tag already exists: $TAG (use --force to recreate)" >&2
      exit 1
    fi
    git tag -d "$TAG" >/dev/null
  fi
  git tag "$TAG"
  echo "created: $TAG"
fi
