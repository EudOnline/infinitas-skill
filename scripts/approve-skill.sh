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
python3 - "$DIR" "$REVIEWER" "$DECISION" "$NOTE" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
skill_dir = Path(sys.argv[1])
reviewer, decision, note = sys.argv[2:5]
meta_path = skill_dir / '_meta.json'
reviews_path = skill_dir / 'reviews.json'
meta = json.loads(meta_path.read_text(encoding='utf-8'))
if reviews_path.exists():
    reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
else:
    reviews = {'version': 1, 'requests': [], 'entries': []}
reviews.setdefault('requests', [])
reviews.setdefault('entries', [])
reviews['entries'].append({
    'reviewer': reviewer,
    'decision': decision,
    'note': note or None,
    'at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
})
meta['review_state'] = 'approved' if decision == 'approved' else 'rejected'
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
reviews_path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{decision}: {skill_dir} by {reviewer}')
PY
