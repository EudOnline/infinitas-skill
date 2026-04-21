#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/repair-installed-skill.sh <skill-name> <target-dir>" >&2
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

NAME="$1"
TARGET_DIR="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INFO_JSON="$(python3 - <<'PY' "$ROOT" "$TARGET_DIR" "$NAME"
import json
import sys

sys.path.insert(0, sys.argv[1] + '/scripts')
from installed_skill_lib import InstalledSkillError, load_installed_skill  # noqa: E402

try:
    _manifest, item = load_installed_skill(sys.argv[2], sys.argv[3])
except InstalledSkillError as exc:
    print(json.dumps({'ok': False, 'state': 'failed', 'message': str(exc)}, ensure_ascii=False))
    raise SystemExit(1)

version = item.get('locked_version') or item.get('installed_version') or item.get('version')
qualified_name = item.get('source_qualified_name') or item.get('qualified_name') or item.get('name')
registry = item.get('source_registry') or 'self'
payload = {
    'qualified_name': qualified_name,
    'version': version,
    'registry': registry,
}
print(json.dumps(payload, ensure_ascii=False))
PY
)" || {
  status=$?
  printf '%s\n' "$INFO_JSON"
  exit $status
}

TARGET_VERSION="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get('version') or '')
PY
)"
QUALIFIED_NAME="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get('qualified_name') or '')
PY
)"
SOURCE_REGISTRY="$(python3 - <<'PY' "$INFO_JSON"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get('registry') or 'self')
PY
)"

[[ -n "$TARGET_VERSION" ]] || { echo "could not determine repair target version" >&2; exit 1; }

SWITCH_OUTPUT="$(env PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m infinitas_skill.cli.main install switch "$NAME" "$TARGET_DIR" --to-version "$TARGET_VERSION" --registry "$SOURCE_REGISTRY" --qualified-name "$QUALIFIED_NAME" --force --json)" || {
  status=$?
  printf '%s\n' "$SWITCH_OUTPUT"
  exit $status
}

printf '%s\n' "$SWITCH_OUTPUT"
echo "repaired: $QUALIFIED_NAME@$TARGET_VERSION from $SOURCE_REGISTRY"
