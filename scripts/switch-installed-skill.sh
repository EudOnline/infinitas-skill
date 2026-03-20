#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/switch-installed-skill.sh <skill-name> [target-dir] (--to-active | --to-version X.Y.Z) [--registry NAME] [--qualified-name NAME] [--force]" >&2
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
SOURCE_REGISTRY_OVERRIDE=""
QUALIFIED_NAME_OVERRIDE=""
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
    --registry)
      SOURCE_REGISTRY_OVERRIDE="${2:-}"
      [[ -n "$SOURCE_REGISTRY_OVERRIDE" ]] || { echo "missing value for --registry" >&2; exit 1; }
      shift 2
      ;;
    --qualified-name)
      QUALIFIED_NAME_OVERRIDE="${2:-}"
      [[ -n "$QUALIFIED_NAME_OVERRIDE" ]] || { echo "missing value for --qualified-name" >&2; exit 1; }
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
if [[ $TO_ACTIVE -eq 0 && -z "$TO_VERSION" ]]; then
  usage
  exit 1
fi
if [[ $TO_ACTIVE -eq 1 && -n "$TO_VERSION" ]]; then
  echo "choose either --to-active or --to-version" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEANUP_DIRS=()

freshness_gate_json() {
  python3 - <<'PY' "$ROOT" "$TARGET_DIR" "$NAME"
import json
import sys

sys.path.insert(0, sys.argv[1] + '/scripts')
from install_integrity_policy_lib import load_install_integrity_policy  # noqa: E402
from installed_integrity_lib import evaluate_installed_mutation_readiness  # noqa: E402
from installed_skill_lib import InstalledSkillError, load_installed_skill  # noqa: E402

try:
    _manifest, item = load_installed_skill(sys.argv[2], sys.argv[3])
except InstalledSkillError:
    print(
        json.dumps(
            {
                'freshness_state': 'never-verified',
                'blocking': False,
                'mutation_readiness': 'ready',
                'mutation_policy': None,
                'mutation_reason_code': None,
                'recovery_action': 'reinstall',
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0)

policy = load_install_integrity_policy(sys.argv[1])
payload = evaluate_installed_mutation_readiness(item, policy=policy)
print(json.dumps(payload, ensure_ascii=False))
PY
}

format_freshness_warning() {
  local warning="$1"
  local formatted
  if [[ -z "$warning" ]]; then
    return 0
  fi
  formatted="${warning//<target-dir>/$TARGET_DIR}"
  formatted="${formatted//<skill>/$NAME}"
  printf '%s\n' "$formatted"
}

guard_drifted_install() {
  local skill_name="$1"
  local target_dir="$2"
  local output status
  if [[ $FORCE -eq 1 ]]; then
    return 0
  fi
  if output="$(python3 - <<'PY' "$ROOT" "$target_dir" "$skill_name"
import json
import sys

sys.path.insert(0, sys.argv[1] + '/scripts')
from installed_integrity_lib import InstalledIntegrityError, verify_installed_skill  # noqa: E402

try:
    payload = verify_installed_skill(sys.argv[2], sys.argv[3], root=sys.argv[1])
except InstalledIntegrityError:
    raise SystemExit(0)

if payload.get('state') == 'drifted':
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(2)
PY
  )"; then
    return 0
  else
    status=$?
  fi
  if [[ $status -eq 2 ]]; then
    echo "installed skill drift detected for $skill_name; run python3 scripts/verify-installed-skill.py $skill_name $target_dir --json or scripts/repair-installed-skill.sh $skill_name $target_dir before overwriting local files" >&2
    return 1
  fi
  return $status
}

guard_mutation_readiness() {
  local freshness_json mutation_readiness blocking warning
  if [[ $FORCE -eq 1 ]]; then
    return 0
  fi
  freshness_json="$(freshness_gate_json)"
  mutation_readiness="$(python3 - <<'PY' "$freshness_json"
import json, sys
print(json.loads(sys.argv[1]).get('mutation_readiness') or 'ready')
PY
)"
  [[ "$mutation_readiness" == "ready" ]] && return 0
  blocking="$(python3 - <<'PY' "$freshness_json"
import json, sys
print('1' if json.loads(sys.argv[1]).get('blocking') else '0')
PY
)"
  warning="$(python3 - <<'PY' "$freshness_json"
import json, sys
print(json.loads(sys.argv[1]).get('warning') or '')
PY
)"
  warning="$(format_freshness_warning "$warning")"
  if [[ -n "$warning" ]]; then
    echo "$warning" >&2
  fi
  [[ "$blocking" != "1" ]]
}

cleanup_materialized() {
  local dir
  for dir in "${CLEANUP_DIRS[@]}"; do
    [[ -n "$dir" && -d "$dir" ]] || continue
    rm -rf "$dir"
  done
}

remember_cleanup_dir() {
  local dir="$1"
  [[ -n "$dir" && "$dir" != "null" ]] || return 0
  CLEANUP_DIRS+=("$dir")
}

materialize_source() {
  python3 "$ROOT/scripts/materialize-skill-source.py" --source-json "$1"
}

trap cleanup_materialized EXIT

DEST="$TARGET_DIR/$NAME"
[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }
guard_drifted_install "$NAME" "$TARGET_DIR"
guard_mutation_readiness

RESOLVE_NAME="$QUALIFIED_NAME_OVERRIDE"
[[ -n "$RESOLVE_NAME" ]] || RESOLVE_NAME="$NAME"
ARGS=("$RESOLVE_NAME" --json)
if [[ -n "$TO_VERSION" ]]; then
  ARGS+=(--version "$TO_VERSION")
fi
if [[ -n "$SOURCE_REGISTRY_OVERRIDE" ]]; then
  ARGS+=(--registry "$SOURCE_REGISTRY_OVERRIDE")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
SOURCE_JSON="$(materialize_source "$INFO_JSON")"
SRC="$(python3 - <<'PY' "$SOURCE_JSON"
import json, sys
print(json.loads(sys.argv[1])['materialized_path'])
PY
)"
ROOT_CLEANUP_DIR="$(python3 - <<'PY' "$SOURCE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('cleanup_dir') or '')
PY
)"
remember_cleanup_dir "$ROOT_CLEANUP_DIR"
LOCK_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
info=json.loads(sys.argv[1])
print(info.get('version') or '')
PY
)"
SOURCE_REGISTRY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
info=json.loads(sys.argv[1])
print(info.get('registry_name') or 'self')
PY
)"

"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null
"$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$SOURCE_JSON" >/dev/null 2>&1 || { echo "switch target failed dependency/conflict checks" >&2; "$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$SOURCE_JSON"; exit 1; }
rm -rf "$DEST"
cp -R "$SRC" "$DEST"
python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$SRC" "$DEST" switch "$LOCK_VERSION" "$SOURCE_JSON" >/dev/null
echo "switched: $DEST <- $SRC"
