#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/rollback-installed-skill.sh <skill-name> [target-dir] [--steps N] [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

NAME="$1"
shift || true
TARGET_DIR="$HOME/.openclaw/skills"
STEPS=1
FORCE=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --steps)
      STEPS="${2:-}"
      [[ "$STEPS" =~ ^[0-9]+$ ]] || { echo "--steps must be an integer" >&2; exit 1; }
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

MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$MANIFEST" ]] || { echo "missing manifest: $MANIFEST" >&2; exit 1; }

ROLLBACK_INFO=()
while IFS= read -r line; do
  ROLLBACK_INFO+=("$line")
done < <(python3 - "$ROOT" "$MANIFEST" "$NAME" "$STEPS" <<'PY'
import os
import sys

sys.path.insert(0, os.path.join(sys.argv[1], 'scripts'))
from install_manifest_lib import InstallManifestError, load_install_manifest

_manifest_root, manifest_path, name, steps = sys.argv[1:5]
steps = int(steps)
try:
    manifest = load_install_manifest(manifest_path)
except InstallManifestError as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)

history = list((manifest.get('history') or {}).get(name) or [])
if len(history) < steps:
    raise SystemExit(f'not enough history entries for {name}; have {len(history)}, need {steps}')
item = history[-steps]
print(item.get('locked_version') or item.get('source_version') or item.get('version') or '')
print(item.get('source_registry') or '')
print(item.get('source_qualified_name') or item.get('qualified_name') or '')
PY
)
TARGET_VERSION="${ROLLBACK_INFO[0]}"
ROLLBACK_REGISTRY="${ROLLBACK_INFO[1]}"
ROLLBACK_QUALIFIED_NAME="${ROLLBACK_INFO[2]}"
[[ -n "$TARGET_VERSION" ]] || { echo "could not determine rollback target version" >&2; exit 1; }

ARGS=("$NAME" "$TARGET_DIR" --to-version "$TARGET_VERSION")
if [[ -n "$ROLLBACK_REGISTRY" ]]; then
  ARGS+=(--registry "$ROLLBACK_REGISTRY")
fi
if [[ -n "$ROLLBACK_QUALIFIED_NAME" ]]; then
  ARGS+=(--qualified-name "$ROLLBACK_QUALIFIED_NAME")
fi
if [[ $FORCE -eq 1 ]]; then
  ARGS+=(--force)
fi
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/switch-installed-skill.sh" "${ARGS[@]}"
