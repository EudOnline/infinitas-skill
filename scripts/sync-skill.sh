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
CLEANUP_DIRS=()

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

MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"

INFO=()
while IFS= read -r line; do
  INFO+=("$line")
done < <(python3 - "$ROOT" "$MANIFEST" "$NAME" <<'PY'
import os
import sys

sys.path.insert(0, os.path.join(sys.argv[1], 'scripts'))
from install_manifest_lib import InstallManifestError, load_install_manifest

_manifest_root, manifest_path, name = sys.argv[1:4]
item = {}
if os.path.isfile(manifest_path):
    try:
        manifest = load_install_manifest(manifest_path)
    except InstallManifestError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    skills = manifest.get('skills') or {}
    item = skills.get(name) or {}
    if not item:
        for candidate in skills.values():
            if not isinstance(candidate, dict):
                continue
            if candidate.get('qualified_name') == name or candidate.get('name') == name:
                item = candidate
                break
print(item.get('locked_version') or '')
print(item.get('version') or '')
print(item.get('source_stage') or '')
print(item.get('source_registry') or '')
print(item.get('name') or name)
print(item.get('source_qualified_name') or item.get('qualified_name') or '')
print(item.get('qualified_name') or item.get('name') or name)
PY
)
LOCKED_VERSION="${INFO[0]}"
INSTALLED_VERSION="${INFO[1]}"
SOURCE_STAGE="${INFO[2]}"
MANIFEST_REGISTRY="${INFO[3]}"
INSTALLED_NAME="${INFO[4]}"
SOURCE_QUALIFIED_NAME="${INFO[5]}"
DISPLAY_NAME="${INFO[6]}"
DEST="$TARGET_DIR/$INSTALLED_NAME"

[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }
guard_drifted_install "$NAME" "$TARGET_DIR"

RESOLVE_NAME="$SOURCE_QUALIFIED_NAME"
[[ -n "$RESOLVE_NAME" ]] || RESOLVE_NAME="$NAME"
ARGS=("$RESOLVE_NAME" --json)
if [[ -n "$LOCKED_VERSION" ]]; then
  ARGS+=(--version "$LOCKED_VERSION")
fi
if [[ -n "$MANIFEST_REGISTRY" ]]; then
  ARGS+=(--registry "$MANIFEST_REGISTRY")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
MATERIALIZED_JSON="$(materialize_source "$INFO_JSON")"
SRC="$(python3 - <<'PY' "$MATERIALIZED_JSON"
import json, sys
print(json.loads(sys.argv[1])['materialized_path'])
PY
)"
ROOT_CLEANUP_DIR="$(python3 - <<'PY' "$MATERIALIZED_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('cleanup_dir') or '')
PY
)"
remember_cleanup_dir "$ROOT_CLEANUP_DIR"
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
display = info.get('qualified_name') or info.get('name')
summary = f"resolved: {display}@{info.get('version') or '?'} from {info.get('registry_name')}"
if commit:
    summary += f" @{commit[:12]}"
if tag:
    summary += f" tag={tag}"
elif ref:
    summary += f" ref={ref}"
print(summary)
PY

if [[ $FORCE -ne 1 ]]; then
  echo "source version: $SRC_VERSION ($SRC_STAGE)"
  echo "installed version: $INSTALLED_VERSION ($SOURCE_STAGE)"
  echo "source registry: $SOURCE_REGISTRY"
fi

PLAN_JSON="$(python3 "$ROOT/scripts/resolve-install-plan.py" --skill-dir "$SRC" --target-dir "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$MATERIALIZED_JSON" --mode sync --json)"

python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
root = plan.get('root') or {}
root_display = root.get('qualified_name') or root.get('name')
print(f"resolution plan: {root_display}@{root.get('version')} from {root.get('registry')}")
for step in plan.get('steps', []):
    display = step.get('qualified_name') or step.get('name')
    head = f"- [{step.get('action')}] {display}@{step.get('version')} ({step.get('stage')}) from {step.get('registry')}"
    if step.get('source_commit'):
        head += f" @{step.get('source_commit')[:12]}"
    elif step.get('source_tag'):
        head += f" tag={step.get('source_tag')}"
    elif step.get('source_ref'):
        head += f" ref={step.get('source_ref')}"
    print(head)
    for requester in step.get('requested_by', []):
        registry = f" [{requester.get('registry')}]" if requester.get('registry') else ''
        incubating = ' +incubating' if requester.get('allow_incubating') else ''
        requester_name = requester.get('by_qualified_name') or requester.get('by')
        print(f"    requested by {requester_name}@{requester.get('version')} -> {requester.get('constraint')}{registry}{incubating}")
PY

APPLIED=0
while IFS=$'\t' read -r STEP_ORDER STEP_NAME STEP_VERSION STEP_REGISTRY STEP_STAGE STEP_ACTION STEP_PATH STEP_QUALIFIED STEP_ROOT STEP_NEEDS; do
  [[ -n "$STEP_NAME" ]] || continue
  [[ "$STEP_NEEDS" == "1" ]] || continue
  STEP_DEST="$TARGET_DIR/$STEP_NAME"
  RESOLVE_NAME="$STEP_QUALIFIED"
  [[ -n "$RESOLVE_NAME" ]] || RESOLVE_NAME="$STEP_NAME"
  RESOLVE_ARGS=("$RESOLVE_NAME" --version "$STEP_VERSION" --registry "$STEP_REGISTRY" --json)
  if [[ "$STEP_STAGE" == "incubating" ]]; then
    RESOLVE_ARGS+=(--allow-incubating)
  fi
  STEP_INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${RESOLVE_ARGS[@]}")"
  STEP_SOURCE_JSON="$(materialize_source "$STEP_INFO_JSON")"
  STEP_SRC="$(python3 - <<'PY' "$STEP_SOURCE_JSON"
import json, sys
print(json.loads(sys.argv[1])['materialized_path'])
PY
  )"
  STEP_CLEANUP_DIR="$(python3 - <<'PY' "$STEP_SOURCE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('cleanup_dir') or '')
PY
  )"
  remember_cleanup_dir "$STEP_CLEANUP_DIR"
  "$ROOT/scripts/check-skill.sh" "$STEP_SRC" >/dev/null
  if [[ -e "$STEP_DEST" ]]; then
    rm -rf "$STEP_DEST"
  fi
  cp -R "$STEP_SRC" "$STEP_DEST"
  STEP_PLAN_JSON=""
  if [[ "$STEP_ROOT" == "1" ]]; then
    STEP_PLAN_JSON="$PLAN_JSON"
  fi
  python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$STEP_SRC" "$STEP_DEST" "$STEP_ACTION" "$STEP_VERSION" "$STEP_SOURCE_JSON" "$STEP_PLAN_JSON" >/dev/null
  APPLIED=1
done < <(python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
for step in plan.get('steps', []):
    print('\t'.join([
        str(step.get('order') or ''),
        step.get('name') or '',
        step.get('version') or '',
        step.get('registry') or '',
        step.get('stage') or '',
        step.get('action') or '',
        step.get('path') or '',
        step.get('qualified_name') or '',
        '1' if step.get('root') else '0',
        '1' if step.get('needs_apply') else '0',
    ]))
PY
)

python3 "$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$MATERIALIZED_JSON" --mode sync >/dev/null

if [[ $APPLIED -eq 0 ]]; then
  echo "already up to date: $DEST"
else
  echo "synced plan applied: $DISPLAY_NAME -> $TARGET_DIR"
fi
