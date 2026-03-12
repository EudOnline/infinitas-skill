#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/export-openclaw-skill.sh <qualified-name-or-name> --out DIR [--version X.Y.Z] [--mode auto|confirm] [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

REQUESTED_NAME="$1"
shift || true
OUT_DIR=""
RESOLVED_VERSION=""
MODE="auto"
FORCE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUT_DIR="${2:-}"
      [[ -n "$OUT_DIR" ]] || { echo "missing value for --out" >&2; exit 1; }
      shift 2
      ;;
    --version)
      RESOLVED_VERSION="${2:-}"
      [[ -n "$RESOLVED_VERSION" ]] || { echo "missing value for --version" >&2; exit 1; }
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      [[ "$MODE" == "auto" || "$MODE" == "confirm" ]] || { echo "--mode must be auto or confirm" >&2; exit 1; }
      shift 2
      ;;
    --force)
      FORCE="1"
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

[[ -n "$OUT_DIR" ]] || { echo "--out is required" >&2; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" "$REQUESTED_NAME" "$OUT_DIR" "$RESOLVED_VERSION" "$MODE" "$FORCE" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
requested = sys.argv[2]
out_dir = Path(sys.argv[3]).expanduser()
requested_version = sys.argv[4] or None
mode = sys.argv[5]
force = sys.argv[6] == '1'

sys.path.insert(0, str(root / 'scripts'))
from openclaw_bridge_lib import (  # noqa: E402
    OpenClawBridgeError,
    export_release_to_directory,
    resolve_ai_release,
)

try:
    selected_skill, resolved_version, version_entry = resolve_ai_release(root, requested, requested_version=requested_version)
    export_dir = (out_dir / (selected_skill.get('name') or requested)).resolve()
    manifest_path = (root / version_entry['manifest_path']).resolve()
    bundle_path = (root / version_entry['bundle_path']).resolve()
    payload = {
        'ok': True,
        'state': 'planned' if mode == 'confirm' else 'exported',
        'name': selected_skill.get('name'),
        'qualified_name': selected_skill.get('qualified_name') or selected_skill.get('name'),
        'resolved_version': resolved_version,
        'manifest_path': str(manifest_path),
        'bundle_path': str(bundle_path),
        'export_dir': str(export_dir),
        'mode': mode,
        'force': force,
        'suggested_publish_command': ['clawhub', 'publish', str(export_dir)],
    }
    if mode == 'confirm':
        temp_export_dir = (root / '.tmp-openclaw-export-preview' / (selected_skill.get('name') or requested)).resolve()
        result = export_release_to_directory(root, manifest_path, temp_export_dir, force=True, public_ready=True)
        payload['public_ready'] = result['public_ready']
        payload['validation_errors'] = result['validation_errors']
        shutil.rmtree(temp_export_dir.parent, ignore_errors=True)
        payload['next_step'] = 'run-export'
    else:
        result = export_release_to_directory(root, manifest_path, export_dir, force=force, public_ready=True)
        payload['files'] = result['files']
        payload['public_ready'] = result['public_ready']
        payload['validation_errors'] = result['validation_errors']
        payload['next_step'] = 'review-or-publish-manually'
    print(json.dumps(payload, ensure_ascii=False))
except OpenClawBridgeError as exc:
    print(json.dumps({
        'ok': False,
        'state': 'failed',
        'error_code': 'export-openclaw-failed',
        'message': str(exc),
        'suggested_action': 'check the requested version and published distribution artifacts',
    }, ensure_ascii=False))
    raise SystemExit(1)
PY
