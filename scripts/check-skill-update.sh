#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/check-skill-update.sh <installed-name> <target-dir>" >&2
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
    print(json.dumps({'ok': False, 'state': 'failed', 'error_code': 'installed-skill-not-found', 'message': str(exc)}, ensure_ascii=False))
    raise SystemExit(1)

payload = {
    'name': item.get('name'),
    'qualified_name': item.get('source_qualified_name') or item.get('qualified_name') or item.get('name'),
    'source_registry': item.get('source_registry') or 'self',
    'installed_version': item.get('installed_version') or item.get('version'),
    'integrity': item.get('integrity'),
    'integrity_capability': item.get('integrity_capability'),
    'integrity_reason': item.get('integrity_reason'),
    'last_checked_at': item.get('last_checked_at'),
    'source_distribution_manifest': item.get('source_distribution_manifest'),
    'source_attestation_path': item.get('source_attestation_path'),
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

PULL_JSON="$(./scripts/pull-skill.sh "$QUALIFIED_NAME" "$TARGET_DIR" --registry "$SOURCE_REGISTRY" --mode confirm)" || {
  status=$?
  printf '%s\n' "$PULL_JSON"
  exit $status
}

INTEGRITY_JSON=""
if INTEGRITY_JSON="$(python3 "$ROOT/scripts/verify-installed-skill.py" "$NAME" "$TARGET_DIR" --json)"; then
  :
else
  integrity_status=$?
  if [[ -z "$INTEGRITY_JSON" ]]; then
    INTEGRITY_JSON='{}'
  fi
fi

python3 - <<'PY' "$ROOT" "$INFO_JSON" "$PULL_JSON" "$INTEGRITY_JSON"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_update_explanation  # noqa: E402
from install_integrity_policy_lib import load_install_integrity_policy  # noqa: E402
from installed_integrity_lib import build_installed_integrity_report_item  # noqa: E402
info = json.loads(sys.argv[2])
pull = json.loads(sys.argv[3])
integrity = json.loads(sys.argv[4]) if sys.argv[4] else {}
if not isinstance(integrity, dict) or integrity.get('state') == 'failed':
    integrity = info.get('integrity') or {'state': 'unknown'}
policy = load_install_integrity_policy(sys.argv[1])
report_item = build_installed_integrity_report_item(
    info.get('name') or info.get('qualified_name') or 'installed-skill',
    {
        'name': info.get('name'),
        'source_qualified_name': info.get('qualified_name'),
        'installed_version': info.get('installed_version'),
        'integrity': integrity,
        'integrity_capability': info.get('integrity_capability'),
        'integrity_reason': info.get('integrity_reason'),
        'last_checked_at': info.get('last_checked_at'),
        'source_distribution_manifest': info.get('source_distribution_manifest'),
        'source_attestation_path': info.get('source_attestation_path'),
    },
    policy=policy,
)
latest = pull.get('resolved_version')
installed = info.get('installed_version')
next_step = 'run upgrade-skill' if latest and latest != installed else 'use-installed-skill'
if report_item.get('recovery_action') == 'refresh' and report_item.get('mutation_readiness') in {'warning', 'blocked'}:
    next_step = 'refresh-installed-integrity'
elif report_item.get('recovery_action') == 'repair' and report_item.get('mutation_readiness') in {'warning', 'blocked'}:
    next_step = 'repair-installed-skill'
elif report_item.get('recovery_action') == 'reinstall' and report_item.get('mutation_readiness') in {'warning', 'blocked'}:
    next_step = 'reinstall-installed-skill'
elif report_item.get('recovery_action') == 'backfill-distribution-manifest' and report_item.get('mutation_readiness') in {'warning', 'blocked'}:
    next_step = 'backfill-distribution-manifest'
payload = {
    'ok': True,
    'qualified_name': info.get('qualified_name'),
    'source_registry': info.get('source_registry'),
    'installed_version': installed,
    'latest_available_version': latest,
    'update_available': bool(latest and latest != installed),
    'state': 'update-available' if latest and latest != installed else 'up-to-date',
    'next_step': next_step,
    'integrity': integrity,
    'freshness_state': report_item.get('freshness_state'),
    'checked_age_seconds': report_item.get('checked_age_seconds'),
    'last_checked_at': report_item.get('last_checked_at'),
    'recommended_action': report_item.get('recommended_action'),
    'freshness_policy': report_item.get('freshness_policy'),
    'freshness_warning': report_item.get('freshness_warning'),
    'mutation_readiness': report_item.get('mutation_readiness'),
    'mutation_policy': report_item.get('mutation_policy'),
    'mutation_reason_code': report_item.get('mutation_reason_code'),
    'recovery_action': report_item.get('recovery_action'),
}
payload['explanation'] = build_update_explanation(info, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
