#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/request-review.sh <skill-name-or-path> [--note TEXT]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
NOTE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
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
python3 - "$DIR" "$NOTE" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
skill_dir = Path(sys.argv[1])
note = sys.argv[2]
meta_path = skill_dir / '_meta.json'
reviews_path = skill_dir / 'reviews.json'
meta = json.loads(meta_path.read_text(encoding='utf-8'))
meta['review_state'] = 'under-review'
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if reviews_path.exists():
    reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
else:
    reviews = {'version': 1, 'requests': [], 'entries': []}
reviews.setdefault('requests', [])
reviews.setdefault('entries', [])
reviews['requests'].append({
    'requested_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'note': note or None,
})
reviews_path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'requested review: {skill_dir}')
PY
