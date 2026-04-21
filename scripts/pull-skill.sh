#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/pull-skill.sh <qualified-name-or-name> <target-dir> [--version X.Y.Z] [--registry NAME] [--mode auto|confirm]" >&2
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

REQUESTED_NAME="$1"
TARGET_DIR="$2"
shift 2 || true
RESOLVED_VERSION=""
REGISTRY_NAME=""
MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      RESOLVED_VERSION="${2:-}"
      [[ -n "$RESOLVED_VERSION" ]] || { echo "missing value for --version" >&2; exit 1; }
      shift 2
      ;;
    --registry)
      REGISTRY_NAME="${2:-}"
      [[ -n "$REGISTRY_NAME" ]] || { echo "missing value for --registry" >&2; exit 1; }
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
PLAN_JSON="$(python3 - "$ROOT" "$REQUESTED_NAME" "$TARGET_DIR" "$RESOLVED_VERSION" "$REGISTRY_NAME" "$MODE" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
requested = sys.argv[2]
target_dir = sys.argv[3]
requested_version = sys.argv[4] or None
requested_registry = sys.argv[5] or None
mode = sys.argv[6]

sys.path.insert(0, str(root / 'src'))
sys.path.insert(0, str(root / 'scripts'))
from http_registry_lib import HostedRegistryError, fetch_json, registry_catalog_path  # noqa: E402
from infinitas_skill.discovery.ai_index import validate_ai_index_payload  # noqa: E402
from infinitas_skill.discovery.install_explanation import (  # noqa: E402
    build_pull_failure_explanation,
    build_pull_plan_explanation,
)
from registry_source_lib import find_registry, load_registry_config, normalized_auth, resolve_registry_root  # noqa: E402

resolved_registry_name = 'self'
resolved_registry_root = root
index_path = root / 'catalog' / 'ai-index.json'
payload = None


def fail(error_code, message, suggested_action, *, failed_at_step, qualified_name=None, resolved_version=None, next_step=None, registry_name=None):
    payload = {
        'ok': False,
        'state': 'failed',
        'failed_at_step': failed_at_step,
        'error_code': error_code,
        'message': message,
        'suggested_action': suggested_action,
        'target_dir': target_dir,
    }
    if qualified_name:
        payload['qualified_name'] = qualified_name
    if requested_version is not None:
        payload['requested_version'] = requested_version
    if resolved_version is not None:
        payload['resolved_version'] = resolved_version
    if next_step:
        payload['next_step'] = next_step

    context = {
        'registry_name': registry_name or requested_registry or resolved_registry_name,
        'requested_version': requested_version,
        'resolved_version': resolved_version,
        'requires_confirmation': False,
        'next_step': next_step,
    }
    payload['explanation'] = build_pull_failure_explanation(context, payload)
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(1)

if requested_registry:
    cfg = load_registry_config(root)
    reg = find_registry(cfg, requested_registry)
    if not reg:
        fail(
            'unknown-registry',
            f'unknown registry {requested_registry!r}',
            'use scripts/list-registry-sources.py',
            failed_at_step='resolved',
            registry_name=requested_registry,
        )
    if reg.get('enabled') is False:
        fail(
            'registry-disabled',
            f'registry {requested_registry!r} is disabled',
            'enable the registry in config/registry-sources.json',
            failed_at_step='resolved',
            registry_name=requested_registry,
        )
    resolved_registry_name = requested_registry
    if reg.get('kind') == 'http':
        auth = normalized_auth(reg)
        try:
            payload = fetch_json(
                reg.get('base_url'),
                registry_catalog_path(reg, 'ai_index'),
                token_env=auth.get('env') if auth.get('mode') == 'token' else None,
            )
            index_path = registry_catalog_path(reg, 'ai_index')
        except HostedRegistryError as exc:
            fail(
                'missing-ai-index',
                str(exc),
                'check the hosted registry URL, auth token, or served catalog paths',
                failed_at_step='resolved',
                registry_name=requested_registry,
            )
        resolved_registry_root = None
    else:
        reg_root = resolve_registry_root(root, reg)
        if reg_root is None or not reg_root.exists():
            fail(
                'registry-root-unavailable',
                f'registry root is unavailable for {requested_registry!r}',
                'sync or configure the registry root first',
                failed_at_step='resolved',
                registry_name=requested_registry,
            )
        resolved_registry_root = reg_root
        index_path = reg_root / 'catalog' / 'ai-index.json'

if payload is None and not Path(index_path).exists():
    fail(
        'missing-ai-index',
        f'missing AI index: {index_path}',
        'run scripts/build-catalog.sh or sync the target registry cache',
        failed_at_step='resolved',
    )

if payload is None:
    payload = json.loads(Path(index_path).read_text(encoding='utf-8'))
errors = validate_ai_index_payload(payload)
if errors:
    fail(
        'invalid-ai-index',
        '; '.join(errors),
        'regenerate and validate catalog/ai-index.json',
        failed_at_step='resolved',
    )

policy = payload.get('install_policy') or {}
if policy.get('mode') != 'immutable-only' or policy.get('direct_source_install_allowed') is not False:
    fail(
        'invalid-install-policy',
        'AI install policy must be immutable-only with direct source installs disabled',
        'fix catalog/ai-index.json install_policy',
        failed_at_step='resolved',
    )

matches = []
for skill in payload.get('skills', []):
    if requested == skill.get('qualified_name') or requested == skill.get('name'):
        matches.append(skill)

if not matches:
    fail(
        'skill-not-found',
        f'no AI-index entry found for {requested}',
        'check the skill name or regenerate catalog/ai-index.json',
        failed_at_step='resolved',
    )

exact = [skill for skill in matches if requested == skill.get('qualified_name')]
if exact:
    selected_skill = exact[0]
elif len(matches) == 1:
    selected_skill = matches[0]
else:
    choices = ', '.join(sorted(skill.get('qualified_name') or skill.get('name') or '?' for skill in matches))
    fail(
        'ambiguous-skill-name',
        f'ambiguous skill name {requested}: {choices}',
        'use the qualified_name',
        failed_at_step='resolved',
    )

resolved_version = requested_version or selected_skill.get('default_install_version')
versions = selected_skill.get('versions') or {}
if resolved_version not in versions:
    fail(
        'version-not-found',
        f'version {resolved_version!r} is not available for {selected_skill.get("qualified_name") or selected_skill.get("name")}',
        'use one of available_versions from catalog/ai-index.json',
        failed_at_step='selected_version',
        qualified_name=selected_skill.get('qualified_name') or selected_skill.get('name'),
        resolved_version=resolved_version,
    )

version_entry = versions[resolved_version]
if version_entry.get('installable') is not True:
    fail(
        'version-not-installable',
        f'version {resolved_version!r} is not installable for {selected_skill.get("qualified_name") or selected_skill.get("name")}',
        'pick an installable released version',
        failed_at_step='selected_version',
        qualified_name=selected_skill.get('qualified_name') or selected_skill.get('name'),
        resolved_version=resolved_version,
    )
required_fields = ['manifest_path', 'bundle_path', 'bundle_sha256', 'attestation_path']
missing = [field for field in required_fields if not isinstance(version_entry.get(field), str) or not version_entry.get(field).strip()]
if missing:
    fail(
        'missing-distribution-fields',
        f'missing distribution fields: {", ".join(missing)}',
        'republish the skill and rebuild the catalog',
        failed_at_step='verified_manifest',
        qualified_name=selected_skill.get('qualified_name') or selected_skill.get('name'),
        resolved_version=resolved_version,
    )

if resolved_registry_root is not None:
    for field in ['manifest_path', 'bundle_path', 'attestation_path']:
        full = resolved_registry_root / version_entry[field]
        if not full.exists():
            fail(
                'missing-distribution-file',
                f'missing {field}: {version_entry[field]}',
                'rebuild or republish the distribution artifacts',
                failed_at_step='verified_manifest',
                qualified_name=selected_skill.get('qualified_name') or selected_skill.get('name'),
                resolved_version=resolved_version,
            )

install_name = selected_skill.get('qualified_name') or selected_skill.get('name')
plan = {
    'ok': True,
    'qualified_name': selected_skill.get('qualified_name') or selected_skill.get('name'),
    'requested_version': requested_version,
    'resolved_version': resolved_version,
    'registry_name': resolved_registry_name,
    'registry_root': str(resolved_registry_root) if resolved_registry_root is not None else None,
    'ai_index_path': str(index_path),
    'target_dir': target_dir,
    'state': 'planned' if mode == 'confirm' else 'selected_version',
    'manifest_path': version_entry.get('manifest_path'),
    'bundle_path': version_entry.get('bundle_path'),
    'bundle_sha256': version_entry.get('bundle_sha256'),
    'attestation_path': version_entry.get('attestation_path'),
    'registry_kind': 'http' if resolved_registry_root is None and requested_registry else 'local',
    'install_name': install_name,
    'install_command': ['python3', '-m', 'infinitas_skill.cli.main', 'install', 'exact', install_name, target_dir, '--version', resolved_version] + (['--registry', resolved_registry_name] if requested_registry else []),
    'next_step': 'run-install' if mode == 'auto' else 'confirm-or-run',
}
plan['explanation'] = build_pull_plan_explanation(plan, requested_version=requested_version)
print(json.dumps(plan, ensure_ascii=False))
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

INSTALL_NAME="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
plan = json.loads(sys.argv[1])
print(plan['install_name'])
print(plan['resolved_version'])
PY
)"
INSTALL_NAME="${INSTALL_NAME%%$'
'*}"
RESOLVED_INSTALL_VERSION="$(python3 - <<'PY' "$PLAN_JSON"
import json, sys
print(json.loads(sys.argv[1])['resolved_version'])
PY
)"
LOCKFILE_PATH="$TARGET_DIR/.infinitas-skill-install-manifest.json"
INSTALL_LOG="$(mktemp)"
INSTALL_ARGS=(env "PYTHONPATH=$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m infinitas_skill.cli.main install exact "$INSTALL_NAME" "$TARGET_DIR" --version "$RESOLVED_INSTALL_VERSION" --json)
if [[ -n "$REGISTRY_NAME" ]]; then
  INSTALL_ARGS+=(--registry "$REGISTRY_NAME")
fi
if ! "${INSTALL_ARGS[@]}" >"$INSTALL_LOG" 2>&1; then
  python3 - <<'PY' "$ROOT" "$PLAN_JSON" "$INSTALL_LOG"
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/scripts')
from infinitas_skill.discovery.install_explanation import build_pull_result_explanation  # noqa: E402
plan = json.loads(sys.argv[2])
message = Path(sys.argv[3]).read_text(encoding='utf-8').strip()
payload = {
    'ok': False,
    'qualified_name': plan.get('qualified_name'),
    'requested_version': plan.get('requested_version'),
    'resolved_version': plan.get('resolved_version'),
    'target_dir': plan.get('target_dir'),
    'state': 'failed',
    'failed_at_step': 'materialized',
    'error_code': 'install-failed',
    'message': message,
    'suggested_action': 'inspect install output and distribution artifacts',
}
payload['explanation'] = build_pull_result_explanation(plan, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
  rm -f "$INSTALL_LOG"
  exit 1
fi
rm -f "$INSTALL_LOG"

python3 - <<'PY' "$ROOT" "$PLAN_JSON" "$LOCKFILE_PATH"
import json, sys
sys.path.insert(0, sys.argv[1] + '/src')
sys.path.insert(0, sys.argv[1] + '/scripts')
from infinitas_skill.discovery.install_explanation import build_pull_result_explanation  # noqa: E402
plan = json.loads(sys.argv[2])
lockfile_path = sys.argv[3]
payload = {
    'ok': True,
    'qualified_name': plan.get('qualified_name'),
    'requested_version': plan.get('requested_version'),
    'resolved_version': plan.get('resolved_version'),
    'target_dir': plan.get('target_dir'),
    'state': 'installed',
    'lockfile_path': lockfile_path,
    'installed_files_manifest': lockfile_path,
    'next_step': 'sync-or-use',
}
payload['explanation'] = build_pull_result_explanation(plan, payload)
print(json.dumps(payload, ensure_ascii=False))
PY
