#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/recommend-skill.sh <task-description> [--target-agent <agent>] [--limit N] [--json]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK="$1"
shift || true
TARGET_AGENT=""
LIMIT=5

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-agent)
      TARGET_AGENT="${2:-}"
      [[ -n "$TARGET_AGENT" ]] || { echo "missing value for --target-agent" >&2; exit 1; }
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      [[ "$LIMIT" =~ ^[0-9]+$ ]] || { echo "--limit must be a non-negative integer" >&2; exit 1; }
      shift 2
      ;;
    --json)
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

python3 - <<'PY' "$ROOT" "$TASK" "$TARGET_AGENT" "$LIMIT"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from recommend_skill_lib import recommend_skills  # noqa: E402

print(
    json.dumps(
        recommend_skills(root, task=sys.argv[2], target_agent=sys.argv[3] or None, limit=int(sys.argv[4])),
        ensure_ascii=False,
    )
)
PY
