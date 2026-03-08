#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "usage: scripts/promote-skill.sh <skill-name> [--force]" >&2
  exit 1
fi
shift || true
FORCE=0
for arg in "$@"; do
  [[ "$arg" == "--force" ]] && FORCE=1
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/incubating/$NAME"
DEST="$ROOT/skills/active/$NAME"

[[ -d "$SRC" ]] || { echo "missing incubating skill: $SRC" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC"

python3 - "$SRC/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
if meta.get('review_state') != 'approved':
    print('FAIL: review_state must be approved before promotion', file=sys.stderr)
    sys.exit(1)
PY

if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "active skill already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi
mv "$SRC" "$DEST"
python3 - "$DEST/_meta.json" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, 'r', encoding='utf-8') as f:
    meta = json.load(f)
meta['status'] = 'active'
with open(p, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
    f.write('\n')
PY
"$ROOT/scripts/build-catalog.sh"
echo "promoted: $NAME"
