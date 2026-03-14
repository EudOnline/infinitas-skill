#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUERY=""
PUBLISHER=""
AGENT=""
TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publisher)
      PUBLISHER="${2:-}"
      shift 2
      ;;
    --agent)
      AGENT="${2:-}"
      shift 2
      ;;
    --tag)
      TAG="${2:-}"
      shift 2
      ;;
    *)
      if [[ -z "$QUERY" ]]; then
        QUERY="$1"
        shift
      else
        echo "unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

python3 - <<'PY' "$ROOT" "$QUERY" "$PUBLISHER" "$AGENT" "$TAG"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from search_inspect_lib import search_skills  # noqa: E402

print(json.dumps(search_skills(root, query=sys.argv[2] or None, publisher=sys.argv[3] or None, agent=sys.argv[4] or None, tag=sys.argv[5] or None), ensure_ascii=False))
PY
