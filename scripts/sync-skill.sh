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
DEST="$TARGET_DIR/$NAME"
MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"

[[ -d "$DEST" ]] || { echo "skill is not installed yet: $DEST" >&2; exit 1; }

readarray -t INFO < <(python3 - "$MANIFEST" "$NAME" <<'PY'
import json, os, sys
manifest_path, name = sys.argv[1:3]
item = {}
if os.path.isfile(manifest_path):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    item = (manifest.get('skills') or {}).get(name) or {}
print(item.get('locked_version') or '')
print(item.get('version') or '')
print(item.get('source_stage') or '')
print(item.get('source_registry') or '')
PY
)
LOCKED_VERSION="${INFO[0]}"
INSTALLED_VERSION="${INFO[1]}"
SOURCE_STAGE="${INFO[2]}"
MANIFEST_REGISTRY="${INFO[3]}"

ARGS=("$NAME" --json)
if [[ -n "$LOCKED_VERSION" ]]; then
  ARGS+=(--version "$LOCKED_VERSION")
fi
if [[ -n "$MANIFEST_REGISTRY" ]]; then
  ARGS+=(--registry "$MANIFEST_REGISTRY")
fi
INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${ARGS[@]}")"
SRC="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1])['path'])
PY
)"
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

PLAN_JSON="$(python3 "$ROOT/scripts/resolve-install-plan.py" --skill-dir "$SRC" --target-dir "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$INFO_JSON" --mode sync --json)"

python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
root = plan.get('root') or {}
print(f"resolution plan: {root.get('name')}@{root.get('version')} from {root.get('registry')}")
for step in plan.get('steps', []):
    head = f"- [{step.get('action')}] {step.get('name')}@{step.get('version')} ({step.get('stage')}) from {step.get('registry')}"
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
        print(f"    requested by {requester.get('by')}@{requester.get('version')} -> {requester.get('constraint')}{registry}{incubating}")
PY

APPLIED=0
while IFS=$'\t' read -r STEP_ORDER STEP_NAME STEP_VERSION STEP_REGISTRY STEP_STAGE STEP_ACTION STEP_PATH STEP_ROOT STEP_NEEDS; do
  [[ -n "$STEP_NAME" ]] || continue
  [[ "$STEP_NEEDS" == "1" ]] || continue
  STEP_DEST="$TARGET_DIR/$STEP_NAME"
  "$ROOT/scripts/check-skill.sh" "$STEP_PATH" >/dev/null
  RESOLVE_ARGS=("$STEP_NAME" --version "$STEP_VERSION" --registry "$STEP_REGISTRY" --json)
  if [[ "$STEP_STAGE" == "incubating" ]]; then
    RESOLVE_ARGS+=(--allow-incubating)
  fi
  STEP_INFO_JSON="$(python3 "$ROOT/scripts/resolve-skill-source.py" "${RESOLVE_ARGS[@]}")"
  if [[ -e "$STEP_DEST" ]]; then
    rm -rf "$STEP_DEST"
  fi
  cp -R "$STEP_PATH" "$STEP_DEST"
  STEP_PLAN_JSON=""
  if [[ "$STEP_ROOT" == "1" ]]; then
    STEP_PLAN_JSON="$PLAN_JSON"
  fi
  python3 "$ROOT/scripts/update-install-manifest.py" "$TARGET_DIR" "$STEP_PATH" "$STEP_DEST" "$STEP_ACTION" "$STEP_VERSION" "$STEP_INFO_JSON" "$STEP_PLAN_JSON" >/dev/null
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
        '1' if step.get('root') else '0',
        '1' if step.get('needs_apply') else '0',
    ]))
PY
)

python3 "$ROOT/scripts/check-install-target.py" "$SRC" "$TARGET_DIR" --source-registry "$SOURCE_REGISTRY" --source-json "$INFO_JSON" --mode sync >/dev/null

if [[ $APPLIED -eq 0 ]]; then
  echo "already up to date: $DEST"
else
  echo "synced plan applied: $NAME -> $TARGET_DIR"
fi
