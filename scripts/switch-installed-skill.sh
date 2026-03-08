#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/switch-installed-skill.sh <skill-name> [target-dir] (--to-active | --to-version X.Y.Z) [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

NAME="$1"
shift || true
TARGET_DIR="$HOME/.openclaw/skills"
TO_ACTIVE=0
TO_VERSION=""
FORCE=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --to-active)
      TO_ACTIVE=1
      shift
      ;;
    --to-version)
      TO_VERSION="${2:-}"
      [[ -n "$TO_VERSION" ]] || { echo "missing value for --to-version" >&2; exit 1; }
      shift 2
      ;;
    --force)
      FORCE=1
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
if [[ $TO_ACTIVE -eq 0 && -z "$TO_VERSION" ]]; then
  usage
  exit 1
fi
if [[ $TO_ACTIVE -eq 1 && -n "$TO_VERSION" ]]; then
  echo "choose either --to-active or --to-version" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$TARGET_DIR/$NAME"
[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }

ARGS=("$NAME" --json)
if [[ -n "$TO_VERSION" ]]; then
  ARGS+=(--version "$TO_VERSION")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
SRC="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1])['path'])
PY
)"
LOCK_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
info=json.loads(sys.argv[1])
print(info.get('version') or '')
PY
)"

"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null
if [[ -e "$DEST" && $FORCE -ne 1 ]]; then
  echo "target exists: $DEST (use --force to overwrite)" >&2
  exit 1
fi
rm -rf "$DEST"
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" switch "$LOCK_VERSION" >/dev/null
echo "switched: $DEST <- $SRC"
