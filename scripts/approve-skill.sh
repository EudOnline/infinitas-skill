#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/approve-skill.sh <skill-name-or-path> --reviewer NAME [--decision approved|rejected] [--note TEXT]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
REVIEWER=""
DECISION="approved"
NOTE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reviewer)
      REVIEWER="${2:-}"
      shift 2
      ;;
    --decision)
      DECISION="${2:-}"
      shift 2
      ;;
    --note)
      NOTE="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done
[[ -n "$REVIEWER" ]] || { echo "--reviewer is required" >&2; exit 1; }
[[ "$DECISION" == "approved" || "$DECISION" == "rejected" ]] || { echo "invalid decision: $DECISION" >&2; exit 1; }

resolve_skill() {
  local name="$1"
  if [[ -d "$name" && -f "$name/_meta.json" ]]; then
    printf '%s' "$name"
    return
  fi
  for stage in incubating active archived; do
    if [[ -d "$ROOT/skills/$stage/$name" ]]; then
      printf '%s' "$ROOT/skills/$stage/$name"
      return
    fi
  done
  return 1
}

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
python3 - "$ROOT" "$DIR" "$REVIEWER" "$DECISION" "$NOTE" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill_dir = Path(sys.argv[2]).resolve()
reviewer, decision, note = sys.argv[3:6]
sys.path.insert(0, str(root / 'scripts'))

from review_lib import ReviewPolicyError, record_review_decision

try:
    evaluation = record_review_decision(skill_dir, reviewer=reviewer, decision=decision, note=note, root=root)
except ReviewPolicyError as exc:
    for error in exc.errors:
        print(f'FAIL: {error}', file=sys.stderr)
    raise SystemExit(1)
except ValueError as exc:
    print(f'FAIL: {exc}', file=sys.stderr)
    raise SystemExit(1)

print(f"{decision}: {skill_dir} by {reviewer} ({evaluation['effective_review_state']})")
PY
