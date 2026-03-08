#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "usage: scripts/promote-skill.sh <skill-name> [--force] [--snapshot-label TEXT]" >&2
  exit 1
fi
shift || true
FORCE=0
SNAPSHOT_LABEL="promote-overwrite"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --snapshot-label)
      SNAPSHOT_LABEL="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/incubating/$NAME"
DEST="$ROOT/skills/active/$NAME"

[[ -d "$SRC" ]] || { echo "missing incubating skill: $SRC" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC"
"$ROOT/scripts/check-promotion-policy.py" --as-active "$SRC"
"$ROOT/scripts/check-registry-integrity.py" >/dev/null

if [[ -e "$DEST" ]]; then
  if [[ $FORCE -ne 1 ]]; then
    echo "active skill already exists: $DEST (use --force to overwrite)" >&2
    exit 1
  fi
  "$ROOT/scripts/snapshot-active-skill.sh" "$NAME" --label "$SNAPSHOT_LABEL" >/dev/null
  rm -rf "$DEST"
fi
mv "$SRC" "$DEST"
python3 - "$ROOT" "$DEST" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill_dir = Path(sys.argv[2]).resolve()
meta_path = skill_dir / '_meta.json'
with open(meta_path, 'r', encoding='utf-8') as handle:
    meta = json.load(handle)
meta['status'] = 'active'
with open(meta_path, 'w', encoding='utf-8') as handle:
    json.dump(meta, handle, ensure_ascii=False, indent=2)
    handle.write('\n')

sys.path.insert(0, str(root / 'scripts'))
from review_lib import sync_declared_review_state

sync_declared_review_state(skill_dir, root=root, stage='active')
PY
"$ROOT/scripts/build-catalog.sh"
echo "promoted: $NAME"
