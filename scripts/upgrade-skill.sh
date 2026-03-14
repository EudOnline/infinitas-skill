#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/upgrade-skill.sh <installed-name> <target-dir> [--to-version X.Y.Z] [--registry NAME] [--mode auto|confirm]" >&2
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

NAME="$1"
TARGET_DIR="$2"
shift 2 || true
TO_VERSION=""
SOURCE_REGISTRY_OVERRIDE=""
MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --to-version)
      TO_VERSION="${2:-}"
      [[ -n "$TO_VERSION" ]] || { echo "missing value for --to-version" >&2; exit 1; }
      shift 2
      ;;
    --registry)
      SOURCE_REGISTRY_OVERRIDE="${2:-}"
      [[ -n "$SOURCE_REGISTRY_OVERRIDE" ]] || { echo "missing value for --registry" >&2; exit 1; }
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      [[ "$MODE" == "auto" || "$MODE" == "confirm" ]] || { echo "--mode must be auto or confirm" >&2; exit 1; }
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFO_JSON="$(python3 - <<'PY' "$ROOT" "$TARGET_DIR" "$NAME"
import json
import sys

sys.path.insert(0, sys.argv[1] + '/scripts')
from installed_skill_lib import InstalledSkillError, load_installed_skill  # noqa: E402

try:
    _manifest, item = load_installed_skill(sys.argv[2], sys.argv[3])
except InstalledSkillError as exc:
    print(json.dumps({'ok': False, 'state': 'failed', 'error_code': 'installed-skill-not-found', 'message': str(exc)}, ensure_ascii=False))
    raise SystemExit(1)

payload = {
    'name': item.get('name') or sys.argv[3],
    'qualified_name': item.get('source_qualified_name') or item.get('qualified_name') or item.get('name'),
    'source_registry': item.get('source_registry') or 'self',
    'installed_version': item.get('installed_version') or item.get('version'),
}
print(json.dumps(payload, ensure_ascii=False))
PY
)" || {
  status=$?
  printf '%s\n' "$INFO_JSON"
  exit $status
}

QUALIFIED_NAME="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('qualified_name') or '')
PY
)"
SOURCE_REGISTRY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('source_registry') or 'self')
PY
)"
INSTALLED_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('installed_version') or '')
PY
)"

if [[ -n "$SOURCE_REGISTRY_OVERRIDE" && "$SOURCE_REGISTRY_OVERRIDE" != "$SOURCE_REGISTRY" ]]; then
  python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_DIR" "$SOURCE_REGISTRY_OVERRIDE"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
payload = {
    'ok': False,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'target_dir': sys.argv[3],
    'state': 'failed',
    'error_code': 'cross-source-upgrade-not-allowed',
    'message': f"refusing to switch source registry from {info.get('source_registry')!r} to {sys.argv[4]!r}",
    'next_step': 'rerun without --registry or reinstall explicitly from the new source',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 1
fi

PULL_ARGS=(./scripts/pull-skill.sh "$QUALIFIED_NAME" "$TARGET_DIR" --registry "$SOURCE_REGISTRY" --mode confirm)
if [[ -n "$TO_VERSION" ]]; then
  PULL_ARGS=(./scripts/pull-skill.sh "$QUALIFIED_NAME" "$TARGET_DIR" --registry "$SOURCE_REGISTRY" --version "$TO_VERSION" --mode confirm)
fi
PLAN_JSON="$("${PULL_ARGS[@]}")" || {
  status=$?
  printf '%s\n' "$PLAN_JSON"
  exit $status
}

TARGET_VERSION="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('resolved_version') or '')
PY
)"

if [[ "$MODE" == "confirm" ]]; then
  python3 - <<'PY' "$ROOT" "$INFO_JSON" "$PLAN_JSON" "$TARGET_DIR"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
plan = json.loads(sys.argv[3])
payload = {
    'ok': True,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': plan.get('resolved_version'),
    'target_dir': sys.argv[4],
    'state': 'planned',
    'manifest_path': plan.get('manifest_path'),
    'next_step': 'run upgrade-skill',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 0
fi

if [[ -z "$TARGET_VERSION" || "$TARGET_VERSION" == "$INSTALLED_VERSION" ]]; then
  python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_DIR"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
payload = {
    'ok': True,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': info.get('installed_version'),
    'target_dir': sys.argv[3],
    'state': 'up-to-date',
    'manifest_path': None,
    'next_step': 'use-installed-skill',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 0
fi

SWITCH_OUTPUT="$(./scripts/switch-installed-skill.sh "$NAME" "$TARGET_DIR" --to-version "$TARGET_VERSION" --registry "$SOURCE_REGISTRY" --qualified-name "$QUALIFIED_NAME" --force)" || {
  status=$?
  printf '%s\n' "$SWITCH_OUTPUT"
  exit $status
}

python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_VERSION" "$TARGET_DIR"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
payload = {
    'ok': True,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': sys.argv[3],
    'target_dir': sys.argv[4],
    'state': 'installed',
    'manifest_path': f"{sys.argv[4]}/.infinitas-skill-install-manifest.json",
    'next_step': 'use-installed-skill',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
