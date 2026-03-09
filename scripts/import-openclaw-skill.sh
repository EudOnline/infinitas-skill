#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/import-openclaw-skill.sh <source-dir-or-SKILL.md> [--owner NAME] [--publisher NAME] [--mode auto|confirm] [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SOURCE_PATH="$1"
shift || true
OWNER="${USER:-unknown}"
PUBLISHER=""
MODE="auto"
FORCE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)
      OWNER="${2:-}"
      [[ -n "$OWNER" ]] || { echo "missing value for --owner" >&2; exit 1; }
      shift 2
      ;;
    --publisher)
      PUBLISHER="${2:-}"
      [[ -n "$PUBLISHER" ]] || { echo "missing value for --publisher" >&2; exit 1; }
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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" "$SOURCE_PATH" "$OWNER" "$PUBLISHER" "$MODE" "$FORCE" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
source_value = sys.argv[2]
owner = sys.argv[3]
publisher = sys.argv[4] or None
mode = sys.argv[5]
force = sys.argv[6] == '1'

sys.path.insert(0, str(root / 'scripts'))
from openclaw_bridge_lib import (  # noqa: E402
    OpenClawBridgeError,
    derive_registry_meta,
    parse_skill_frontmatter,
    resolve_skill_dir,
    scaffold_imported_skill,
)

try:
    source_dir = resolve_skill_dir(source_value)
    frontmatter = parse_skill_frontmatter(source_dir / 'SKILL.md')
    meta = derive_registry_meta(frontmatter, owner=owner, publisher=publisher)
    target_dir = root / 'skills' / 'incubating' / meta['name']
    payload = {
        'ok': True,
        'state': 'planned' if mode == 'confirm' else 'imported',
        'source_dir': str(source_dir),
        'target_dir': str(target_dir),
        'name': meta['name'],
        'qualified_name': meta.get('qualified_name') or meta['name'],
        'owner': meta['owner'],
        'publisher': meta.get('publisher'),
        'mode': mode,
        'force': force,
    }
    if mode == 'confirm':
        payload['next_step'] = 'run-import'
    else:
        result = scaffold_imported_skill(source_dir, target_dir, meta, force=force)
        payload['files'] = result['files']
        payload['next_step'] = 'validate-imported-skill'
    print(json.dumps(payload, ensure_ascii=False))
except OpenClawBridgeError as exc:
    print(json.dumps({
        'ok': False,
        'state': 'failed',
        'error_code': 'import-openclaw-failed',
        'message': str(exc),
        'suggested_action': 'fix the source skill or choose a different target name',
    }, ensure_ascii=False))
    raise SystemExit(1)
PY
