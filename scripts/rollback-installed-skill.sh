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
[[ -f "$MANIFEST" ]] || { echo "missing manifest: $MANIFEST" >&2; exit 1; }

readarray -t ROLLBACK_INFO < <(python3 - "$MANIFEST" "$NAME" "$STEPS" <<'PY'
import json, sys
manifest_path, name, steps = sys.argv[1:4]
steps = int(steps)
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)
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
