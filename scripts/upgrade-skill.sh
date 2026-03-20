#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/upgrade-skill.sh <installed-name> <target-dir> [--to-version X.Y.Z] [--registry NAME] [--mode auto|confirm] [--force]" >&2
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
FORCE=0

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
    --force)
      FORCE=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

guard_drifted_install "$NAME" "$TARGET_DIR"

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

FRESHNESS_GATE_JSON="$(freshness_gate_json)"
FRESHNESS_STATE="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('freshness_state') or '')
PY
)"
FRESHNESS_POLICY="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('freshness_policy') or '')
PY
)"
FRESHNESS_WARNING="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('warning') or '')
PY
)"
FRESHNESS_BLOCKING="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print('1' if json.loads(sys.argv[1]).get('blocking') else '0')
PY
)"
MUTATION_READINESS="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('mutation_readiness') or '')
PY
)"
MUTATION_REASON_CODE="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('mutation_reason_code') or '')
PY
)"
RECOVERY_ACTION="$(python3 - <<'PY' "$FRESHNESS_GATE_JSON"
import json, sys
print(json.loads(sys.argv[1]).get('recovery_action') or '')
PY
)"

if [[ $FORCE -eq 1 ]]; then
  FRESHNESS_STATE=""
  FRESHNESS_POLICY=""
  FRESHNESS_WARNING=""
  FRESHNESS_BLOCKING="0"
  MUTATION_READINESS=""
  MUTATION_REASON_CODE=""
  RECOVERY_ACTION=""
fi

if [[ -z "$TARGET_VERSION" || "$TARGET_VERSION" == "$INSTALLED_VERSION" ]]; then
  if [[ "$MODE" == "confirm" ]]; then
    python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_DIR" "$FRESHNESS_STATE" "$FRESHNESS_POLICY" "$FRESHNESS_WARNING" "$MUTATION_READINESS" "$MUTATION_REASON_CODE" "$RECOVERY_ACTION"
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
    'freshness_state': sys.argv[4] or None,
    'freshness_policy': sys.argv[5] or None,
    'freshness_warning': sys.argv[6] or None,
    'mutation_readiness': sys.argv[7] or 'ready',
    'mutation_policy': sys.argv[5] or None,
    'mutation_reason_code': sys.argv[8] or None,
    'recovery_action': sys.argv[9] or 'none',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
    exit 0
  fi
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

if [[ "$MODE" == "confirm" ]]; then
  if [[ "$FRESHNESS_BLOCKING" == "1" ]]; then
    python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_DIR" "$FRESHNESS_WARNING" "$FRESHNESS_STATE" "$FRESHNESS_POLICY" "$MUTATION_REASON_CODE" "$RECOVERY_ACTION"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
recovery_action = sys.argv[8] or None
next_step = {
    'refresh': 'refresh-installed-integrity',
    'reinstall': 'reinstall-installed-skill',
    'backfill-distribution-manifest': 'backfill-distribution-manifest',
}.get(recovery_action, 'refresh-installed-integrity')
payload = {
    'ok': False,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': info.get('installed_version'),
    'target_dir': sys.argv[3],
    'state': 'failed',
    'error_code': sys.argv[7] or 'stale-installed-integrity',
    'message': sys.argv[4],
    'next_step': next_step,
    'freshness_state': sys.argv[5] or None,
    'freshness_policy': sys.argv[6] or None,
    'freshness_warning': sys.argv[4],
    'mutation_readiness': 'blocked',
    'mutation_policy': sys.argv[6] or None,
    'mutation_reason_code': sys.argv[7] or None,
    'recovery_action': recovery_action,
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
    exit 1
  fi
  if [[ "$MUTATION_READINESS" == "warning" ]]; then
    python3 - <<'PY' "$ROOT" "$INFO_JSON" "$PLAN_JSON" "$TARGET_DIR" "$FRESHNESS_POLICY" "$FRESHNESS_WARNING" "$FRESHNESS_STATE" "$MUTATION_REASON_CODE" "$RECOVERY_ACTION"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
plan = json.loads(sys.argv[3])
recovery_action = sys.argv[9] or None
next_step = {
    'refresh': 'refresh-installed-integrity',
    'reinstall': 'reinstall-installed-skill',
    'backfill-distribution-manifest': 'backfill-distribution-manifest',
}.get(recovery_action, 'run upgrade-skill')
payload = {
    'ok': True,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': plan.get('resolved_version'),
    'target_dir': sys.argv[4],
    'state': 'planned',
    'manifest_path': plan.get('manifest_path'),
    'next_step': next_step,
    'freshness_state': sys.argv[7] or None,
    'freshness_policy': sys.argv[5] or None,
    'freshness_warning': sys.argv[6] or None,
    'mutation_readiness': 'warning',
    'mutation_policy': sys.argv[5] or None,
    'mutation_reason_code': sys.argv[8] or None,
    'recovery_action': recovery_action,
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
    exit 0
  fi
  python3 - <<'PY' "$ROOT" "$INFO_JSON" "$PLAN_JSON" "$TARGET_DIR" "$FRESHNESS_STATE" "$FRESHNESS_POLICY" "$FRESHNESS_WARNING" "$MUTATION_READINESS" "$MUTATION_REASON_CODE" "$RECOVERY_ACTION"
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
    'freshness_state': sys.argv[5] or None,
    'freshness_policy': sys.argv[6] or None,
    'freshness_warning': sys.argv[7] or None,
    'mutation_readiness': sys.argv[8] or 'ready',
    'mutation_policy': sys.argv[6] or None,
    'mutation_reason_code': sys.argv[9] or None,
    'recovery_action': sys.argv[10] or 'none',
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 0
fi

if [[ "$MUTATION_READINESS" == "warning" && -n "$FRESHNESS_WARNING" ]]; then
  echo "$FRESHNESS_WARNING" >&2
fi

if [[ "$FRESHNESS_BLOCKING" == "1" ]]; then
  python3 - <<'PY' "$ROOT" "$INFO_JSON" "$TARGET_DIR" "$FRESHNESS_WARNING" "$FRESHNESS_STATE" "$FRESHNESS_POLICY" "$MUTATION_REASON_CODE" "$RECOVERY_ACTION"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_upgrade_explanation  # noqa: E402
info = json.loads(sys.argv[2])
recovery_action = sys.argv[8] or None
next_step = {
    'refresh': 'refresh-installed-integrity',
    'reinstall': 'reinstall-installed-skill',
    'backfill-distribution-manifest': 'backfill-distribution-manifest',
}.get(recovery_action, 'refresh-installed-integrity')
payload = {
    'ok': False,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'from_version': info.get('installed_version'),
    'to_version': info.get('installed_version'),
    'target_dir': sys.argv[3],
    'state': 'failed',
    'error_code': sys.argv[7] or 'stale-installed-integrity',
    'message': sys.argv[4],
    'next_step': next_step,
    'freshness_state': sys.argv[5] or None,
    'freshness_policy': sys.argv[6] or None,
    'freshness_warning': sys.argv[4],
    'mutation_readiness': 'blocked',
    'mutation_policy': sys.argv[6] or None,
    'mutation_reason_code': sys.argv[7] or None,
    'recovery_action': recovery_action,
}
payload['explanation'] = build_upgrade_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 1
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
