#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/request-review.sh <skill-name-or-path> [--note TEXT] [--show-recommendations]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
NOTE=""
SHOW_RECOMMENDATIONS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --note)
      NOTE="${2:-}"
      shift 2
      ;;
    --show-recommendations)
      SHOW_RECOMMENDATIONS=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

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
python3 - "$ROOT" "$DIR" "$NOTE" "$SHOW_RECOMMENDATIONS" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill_dir = Path(sys.argv[2]).resolve()
note = sys.argv[3]
show_recommendations = sys.argv[4] == '1'
sys.path.insert(0, str(root / 'scripts'))

from reviewer_rotation_lib import recommend_reviewers, render_reviewer_recommendations
from review_lib import ReviewPolicyError, request_review

try:
    evaluation = request_review(skill_dir, note=note, root=root)
    recommendations = recommend_reviewers(skill_dir, root=root) if show_recommendations else None
except ReviewPolicyError as exc:
    for error in exc.errors:
        print(f'FAIL: {error}', file=sys.stderr)
    raise SystemExit(1)

print(f"requested review: {skill_dir} ({evaluation['effective_review_state']})")
if recommendations is not None:
    print(render_reviewer_recommendations(recommendations))
PY
