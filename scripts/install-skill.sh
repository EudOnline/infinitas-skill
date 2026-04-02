#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/install-skill.sh <skill-name> [target-dir] [--force] [--version X.Y.Z] [--registry NAME] [--snapshot ID|latest] [--no-deps]" >&2
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
SNAPSHOT=""
AUTO_DEPS=1
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
    --registry)
      REGISTRY="${2:-}"
      [[ -n "$REGISTRY" ]] || { echo "missing value for --registry" >&2; exit 1; }
      shift 2
      ;;
    --snapshot)
      SNAPSHOT="${2:-}"
      [[ -n "$SNAPSHOT" ]] || { echo "missing value for --snapshot" >&2; exit 1; }
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
CLEANUP_DIRS=()

cleanup_materialized() {
  local dir
  if [[ ${#CLEANUP_DIRS[@]} -eq 0 ]]; then
    return 0
  fi
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

ARGS=("$NAME" --json)
if [[ -n "$LOCK_VERSION" ]]; then
  ARGS+=(--version "$LOCK_VERSION")
fi
if [[ -n "$REGISTRY" ]]; then
  ARGS+=(--registry "$REGISTRY")
fi
if [[ -n "$SNAPSHOT" ]]; then
  ARGS+=(--snapshot "$SNAPSHOT")
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
RESOLVED_SNAPSHOT_ID="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('registry_snapshot_id') or '')
PY
)"
RESOLVED_NAME="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('name') or '')
PY
)"
RESOLVED_DISPLAY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
info = json.loads(sys.argv[1])
print(info.get('qualified_name') or info.get('name') or '')
PY
)"
DEST="$TARGET_DIR/$RESOLVED_NAME"

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

mkdir -p "$TARGET_DIR"
PLAN_JSON="$(env PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m infinitas_skill.cli.main install resolve-plan --skill-dir "$SRC" --target-dir "$TARGET_DIR" --source-registry "$RESOLVED_REGISTRY" --source-json "$MATERIALIZED_JSON" --mode install --json)"

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

if [[ $AUTO_DEPS -eq 0 ]]; then
  if python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
for step in plan.get('steps', []):
    if step.get('root'):
        continue
    if step.get('needs_apply'):
        raise SystemExit(1)
PY
  then
    :
  else
    echo "dependency plan requires installing or upgrading dependencies; rerun without --no-deps" >&2
    exit 1
  fi
fi

ROOT_ACTION="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
for step in plan.get('steps', []):
    if step.get('root'):
        print(step.get('action') or '')
        break
PY
)"
if [[ -e "$DEST" && "$ROOT_ACTION" != "keep" && $FORCE -ne 1 ]]; then
  echo "target already exists: $DEST (use --force to overwrite)" >&2
  exit 1
fi

APPLIED=0
while IFS=$'\t' read -r STEP_ORDER STEP_NAME STEP_VERSION STEP_REGISTRY STEP_STAGE STEP_ACTION STEP_PATH STEP_QUALIFIED STEP_ROOT STEP_NEEDS; do
  [[ -n "$STEP_NAME" ]] || continue
  [[ "$STEP_NEEDS" == "1" ]] || continue
  STEP_DEST="$TARGET_DIR/$STEP_NAME"
  if [[ "$STEP_ROOT" == "1" && -e "$STEP_DEST" && $FORCE -ne 1 ]]; then
    echo "target already exists: $STEP_DEST (use --force to overwrite)" >&2
    exit 1
  fi
  RESOLVE_NAME="$STEP_QUALIFIED"
  [[ -n "$RESOLVE_NAME" ]] || RESOLVE_NAME="$STEP_NAME"
  RESOLVE_ARGS=("$RESOLVE_NAME" --version "$STEP_VERSION" --registry "$STEP_REGISTRY" --json)
  if [[ "$STEP_STAGE" == "incubating" ]]; then
    RESOLVE_ARGS+=(--allow-incubating)
  fi
  if [[ -n "$RESOLVED_SNAPSHOT_ID" && "$STEP_REGISTRY" == "$RESOLVED_REGISTRY" ]]; then
    RESOLVE_ARGS+=(--snapshot "$RESOLVED_SNAPSHOT_ID")
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
  STEP_LOCK_VERSION="$STEP_VERSION"
  STEP_PLAN_JSON=""
  if [[ "$STEP_ROOT" == "1" ]]; then
    STEP_LOCK_VERSION="${LOCK_VERSION:-$RESOLVED_VERSION}"
    STEP_PLAN_JSON="$PLAN_JSON"
  fi
  python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$STEP_SRC" "$STEP_DEST" "$STEP_ACTION" "$STEP_LOCK_VERSION" "$STEP_SOURCE_JSON" "$STEP_PLAN_JSON" >/dev/null
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

env PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m infinitas_skill.cli.main install check-target "$SRC" "$TARGET_DIR" --source-registry "$RESOLVED_REGISTRY" --source-json "$MATERIALIZED_JSON" --mode install >/dev/null

if [[ $APPLIED -eq 0 ]]; then
  echo "already satisfied: $DEST"
else
  echo "installed plan applied: $RESOLVED_DISPLAY -> $TARGET_DIR"
fi
