#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/install-by-name.sh <name> <target-dir> [--version X.Y.Z] [--target-agent AGENT] [--mode auto|confirm]" >&2
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

QUERY="$1"
TARGET_DIR="$2"
shift 2 || true
REQUESTED_VERSION=""
TARGET_AGENT=""
MODE="auto"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      REQUESTED_VERSION="${2:-}"
      [[ -n "$REQUESTED_VERSION" ]] || { echo "missing value for --version" >&2; exit 1; }
      shift 2
      ;;
    --target-agent)
      TARGET_AGENT="${2:-}"
      [[ -n "$TARGET_AGENT" ]] || { echo "missing value for --target-agent" >&2; exit 1; }
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

RESOLVE_ARGS=(./scripts/resolve-skill.sh "$QUERY")
if [[ -n "$TARGET_AGENT" ]]; then
  RESOLVE_ARGS+=(--target-agent "$TARGET_AGENT")
fi
RESOLVE_JSON="$("${RESOLVE_ARGS[@]}")"

STATE="$(python3 - <<'PY' "$RESOLVE_JSON"
import json, sys
print((json.loads(sys.argv[1]) or {}).get('state') or '')
PY
)"

if [[ "$STATE" == "ambiguous" || "$STATE" == "not-found" || "$STATE" == "incompatible" || "$STATE" == "failed" ]]; then
  printf '%s\n' "$RESOLVE_JSON"
  exit 1
fi

REQUIRES_CONFIRMATION="$(python3 - <<'PY' "$RESOLVE_JSON"
import json, sys
print('true' if (json.loads(sys.argv[1]) or {}).get('requires_confirmation') else 'false')
PY
)"

if [[ "$MODE" == "auto" && "$REQUIRES_CONFIRMATION" == "true" ]]; then
  python3 - <<'PY' "$ROOT" "$RESOLVE_JSON" "$QUERY" "$TARGET_DIR" "$REQUESTED_VERSION"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_install_explanation  # noqa: E402
resolve_payload = json.loads(sys.argv[2])
resolved = resolve_payload.get('resolved') or {}
payload = {
    'ok': False,
    'query': sys.argv[3],
    'qualified_name': resolved.get('qualified_name'),
    'source_registry': resolved.get('source_registry'),
    'requested_version': sys.argv[5] or None,
    'resolved_version': resolved.get('resolved_version'),
    'target_dir': sys.argv[4],
    'manifest_path': None,
    'state': 'failed',
    'requires_confirmation': True,
    'error_code': 'confirmation-required',
    'next_step': 'rerun with --mode confirm and explicit confirmation',
}
payload['explanation'] = build_install_explanation(resolve_payload, payload, requested_version=payload.get('requested_version'))
print(json.dumps(payload, ensure_ascii=False))
PY
  exit 1
fi

PULL_NAME="$(python3 - <<'PY' "$RESOLVE_JSON"
import json, sys
resolved = (json.loads(sys.argv[1]) or {}).get('resolved') or {}
print(resolved.get('qualified_name') or '')
PY
)"
SOURCE_REGISTRY="$(python3 - <<'PY' "$RESOLVE_JSON"
import json, sys
resolved = (json.loads(sys.argv[1]) or {}).get('resolved') or {}
print(resolved.get('source_registry') or '')
PY
)"
RESOLVED_VERSION="$(python3 - <<'PY' "$RESOLVE_JSON"
import json, sys
resolved = (json.loads(sys.argv[1]) or {}).get('resolved') or {}
print(resolved.get('resolved_version') or '')
PY
)"

PULL_ARGS=(./scripts/pull-skill.sh "$PULL_NAME" "$TARGET_DIR")
if [[ -n "$REQUESTED_VERSION" ]]; then
  PULL_ARGS+=(--version "$REQUESTED_VERSION")
elif [[ -n "$RESOLVED_VERSION" ]]; then
  PULL_ARGS+=(--version "$RESOLVED_VERSION")
fi
if [[ -n "$SOURCE_REGISTRY" ]]; then
  PULL_ARGS+=(--registry "$SOURCE_REGISTRY")
fi
if [[ "$MODE" == "confirm" ]]; then
  PULL_ARGS+=(--mode confirm)
fi

PULL_JSON="$("${PULL_ARGS[@]}")" || {
  status=$?
  printf '%s\n' "$PULL_JSON"
  exit $status
}

python3 - <<'PY' "$ROOT" "$RESOLVE_JSON" "$PULL_JSON" "$QUERY" "$TARGET_DIR" "$REQUESTED_VERSION"
import json, sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from explain_install_lib import build_install_explanation  # noqa: E402
resolve_payload = json.loads(sys.argv[2])
pull_payload = json.loads(sys.argv[3])
resolved = resolve_payload.get('resolved') or {}
payload = {
    'ok': pull_payload.get('ok'),
    'query': sys.argv[4],
    'qualified_name': pull_payload.get('qualified_name') or resolved.get('qualified_name'),
    'source_registry': pull_payload.get('registry_name') or resolved.get('source_registry'),
    'requested_version': sys.argv[6] or pull_payload.get('requested_version'),
    'resolved_version': pull_payload.get('resolved_version') or resolved.get('resolved_version'),
    'target_dir': sys.argv[5],
    'manifest_path': pull_payload.get('lockfile_path') or pull_payload.get('manifest_path'),
    'state': pull_payload.get('state'),
    'requires_confirmation': resolve_payload.get('requires_confirmation'),
    'next_step': 'check-update-or-use' if pull_payload.get('state') == 'installed' else pull_payload.get('next_step'),
}
payload['explanation'] = build_install_explanation(resolve_payload, payload, requested_version=payload.get('requested_version'))
print(json.dumps(payload, ensure_ascii=False))
PY
