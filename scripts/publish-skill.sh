#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/publish-skill.sh <skill-name-or-path> [--version X.Y.Z] [--mode auto|confirm]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

TARGET="$1"
shift || true
ASSERT_VERSION=""
MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      ASSERT_VERSION="${2:-}"
      [[ -n "$ASSERT_VERSION" ]] || { echo "missing value for --version" >&2; exit 1; }
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
PLAN_JSON="$(python3 - "$ROOT" "$TARGET" "$ASSERT_VERSION" "$MODE" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
target = sys.argv[2]
assert_version = sys.argv[3] or None
mode = sys.argv[4]

sys.path.insert(0, str(root / 'scripts'))
from distribution_lib import distribution_paths  # noqa: E402
from skill_identity_lib import normalize_skill_identity  # noqa: E402

skill_dir = None
candidate = Path(target)
if candidate.is_dir() and (candidate / '_meta.json').exists():
    skill_dir = candidate.resolve()
else:
    for stage in ['active', 'incubating', 'archived']:
        path = root / 'skills' / stage / target
        if path.is_dir() and (path / '_meta.json').exists():
            skill_dir = path.resolve()
            break

if skill_dir is None:
    print(json.dumps({
        'ok': False,
        'state': 'failed',
        'failed_at_step': 'resolved',
        'error_code': 'skill-not-found',
        'message': f'cannot resolve skill: {target}',
        'suggested_action': 'use a skill name or path that contains _meta.json',
    }, ensure_ascii=False))
    raise SystemExit(1)

meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
identity = normalize_skill_identity(meta)
name = meta.get('name') or skill_dir.name
version = meta.get('version')
status = meta.get('status') or skill_dir.parent.name
if assert_version and assert_version != version:
    print(json.dumps({
        'ok': False,
        'state': 'failed',
        'failed_at_step': 'versioned',
        'error_code': 'version-mismatch',
        'message': f'--version {assert_version!r} does not match current skill version {version!r}',
        'suggested_action': 'update the skill version or pass the current version',
    }, ensure_ascii=False))
    raise SystemExit(1)
if status == 'archived':
    print(json.dumps({
        'ok': False,
        'state': 'failed',
        'failed_at_step': 'resolved',
        'error_code': 'archived-skill',
        'message': f'cannot publish archived skill {name}',
        'suggested_action': 'promote from incubating or publish an active skill',
    }, ensure_ascii=False))
    raise SystemExit(1)

paths = distribution_paths(root, name, version, publisher=identity.get('publisher'))
manifest_rel = str(paths['manifest_rel'])
bundle_rel = str(paths['bundle_rel'])
attestation_rel = f'catalog/provenance/{name}-{version}.json'
commands = []
if status == 'incubating':
    commands.append(['python3', 'scripts/review-status.py', name, '--as-active', '--require-pass'])
    commands.append(['scripts/promote-skill.sh', name])
commands.append(['scripts/release-skill.sh', name, '--push-tag', '--write-provenance'])
commands.append(['scripts/build-catalog.sh'])

payload = {
    'ok': True,
    'skill': name,
    'qualified_name': identity.get('qualified_name') or name,
    'version': version,
    'status': status,
    'state': 'planned' if mode == 'confirm' else 'resolved',
    'manifest_path': manifest_rel,
    'bundle_path': bundle_rel,
    'attestation_path': attestation_rel,
    'commands': commands,
    'promotion_required': status == 'incubating',
    'next_step': 'confirm-or-run' if mode == 'confirm' else 'publish',
}
print(json.dumps(payload, ensure_ascii=False))
PY
)" || {
  status=$?
  printf '%s\n' "$PLAN_JSON"
  exit $status
}

if [[ "$MODE" == "confirm" ]]; then
  printf '%s\n' "$PLAN_JSON"
  exit 0
fi

SKILL_NAME="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['skill'])
PY
)"
SKILL_STATUS="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['status'])
PY
)"
MANIFEST_PATH="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['manifest_path'])
PY
)"
BUNDLE_PATH="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['bundle_path'])
PY
)"
ATTESTATION_PATH="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['attestation_path'])
PY
)"

run_step() {
  local step="$1"
  shift
  local log
  log="$(mktemp)"
  if ! "$@" >"$log" 2>&1; then
    python3 - <<'PY' "$PLAN_JSON" "$step" "$log"
import json, sys
from pathlib import Path
plan = json.loads(sys.argv[1])
step = sys.argv[2]
message = Path(sys.argv[3]).read_text(encoding='utf-8').strip()
payload = {
    'ok': False,
    'skill': plan.get('skill'),
    'qualified_name': plan.get('qualified_name'),
    'version': plan.get('version'),
    'state': 'failed',
    'failed_at_step': step,
    'error_code': f'{step}-failed',
    'message': message,
    'suggested_action': 'inspect the failing command output and fix the prerequisite',
}
print(json.dumps(payload, ensure_ascii=False))
PY
    rm -f "$log"
    exit 1
  fi
  rm -f "$log"
}

if [[ "$SKILL_STATUS" == "incubating" ]]; then
  run_step reviewed python3 scripts/review-status.py "$SKILL_NAME" --as-active --require-pass
  run_step promoted ./scripts/promote-skill.sh "$SKILL_NAME"
fi
run_step tagged ./scripts/release-skill.sh "$SKILL_NAME" --push-tag --write-provenance
run_step indexed ./scripts/build-catalog.sh

python3 - <<'PY' "$PLAN_JSON" "$ROOT" "$MANIFEST_PATH" "$BUNDLE_PATH" "$ATTESTATION_PATH"
import json, sys
from pathlib import Path
plan = json.loads(sys.argv[1])
root = Path(sys.argv[2]).resolve()
manifest_path = root / sys.argv[3]
bundle_path = root / sys.argv[4]
attestation_path = root / sys.argv[5]
published_at = None
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    published_at = manifest.get('generated_at')
payload = {
    'ok': True,
    'skill': plan.get('skill'),
    'qualified_name': plan.get('qualified_name'),
    'version': plan.get('version'),
    'state': 'published',
    'manifest_path': sys.argv[3],
    'bundle_path': sys.argv[4],
    'attestation_path': sys.argv[5],
    'published_at': published_at,
    'next_step': 'pull-skill',
}
print(json.dumps(payload, ensure_ascii=False))
PY
