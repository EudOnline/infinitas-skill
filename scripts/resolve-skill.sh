#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/resolve-skill.sh <name> [--target-agent <agent>]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

QUERY="$1"
shift || true
TARGET_AGENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-agent)
      TARGET_AGENT="${2:-}"
      [[ -n "$TARGET_AGENT" ]] || { echo "missing value for --target-agent" >&2; exit 1; }
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - <<'PY' "$ROOT" "$QUERY" "$TARGET_AGENT"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
query = sys.argv[2]
target_agent = sys.argv[3] or None

sys.path.insert(0, str(root / 'scripts'))
from discovery_resolver_lib import load_discovery_index, resolve_skill  # noqa: E402
from explain_install_lib import build_resolve_explanation  # noqa: E402

try:
    payload = load_discovery_index(root)
    result = resolve_skill(payload=payload, query=query, target_agent=target_agent)
except Exception as exc:
    result = {
        'ok': False,
        'query': query,
        'state': 'failed',
        'resolved': None,
        'candidates': [],
        'requires_confirmation': False,
        'recommended_next_step': 'fix discovery-index generation',
        'message': str(exc),
    }

result['explanation'] = build_resolve_explanation(result)
print(json.dumps(result, ensure_ascii=False))
PY
