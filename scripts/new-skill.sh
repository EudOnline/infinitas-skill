#!/usr/bin/env bash
set -euo pipefail

NAME_INPUT="${1:-}"
TEMPLATE="${2:-basic}"
TARGET_ROOT="${3:-skills/incubating}"

if [[ -z "$NAME_INPUT" ]]; then
  echo "usage: scripts/new-skill.sh <skill-name|publisher/skill> [basic|scripted|reference-heavy] [target-root]" >&2
  exit 1
fi

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g'
}

PUBLISHER=""
NAME="$NAME_INPUT"
if [[ "$NAME_INPUT" == */* ]]; then
  PUBLISHER="${NAME_INPUT%%/*}"
  NAME="${NAME_INPUT#*/}"
fi

SLUG="$(slugify "$NAME")"
[[ -n "$SLUG" ]] || { echo "invalid skill name" >&2; exit 1; }
PUBLISHER_SLUG=""
if [[ -n "$PUBLISHER" ]]; then
  PUBLISHER_SLUG="$(slugify "$PUBLISHER")"
  [[ -n "$PUBLISHER_SLUG" ]] || { echo "invalid publisher name" >&2; exit 1; }
fi

case "$TEMPLATE" in
  basic) SRC="templates/basic-skill" ; SRC_NAME="basic-skill" ;;
  scripted) SRC="templates/scripted-skill" ; SRC_NAME="scripted-skill" ;;
  reference-heavy) SRC="templates/reference-heavy-skill" ; SRC_NAME="reference-heavy-skill" ;;
  *) echo "unknown template: $TEMPLATE" >&2; exit 1 ;;
esac

DEST="$TARGET_ROOT/$SLUG"
[[ ! -e "$DEST" ]] || { echo "target already exists: $DEST" >&2; exit 1; }
mkdir -p "$TARGET_ROOT"
cp -R "$SRC" "$DEST"

if [[ -f "$DEST/SKILL.md" ]]; then
  sed -i "s/^name: .*/name: $SLUG/" "$DEST/SKILL.md"
fi
if [[ -f "$DEST/_meta.json" ]]; then
  python3 - "$DEST/_meta.json" "$SRC_NAME" "$SLUG" "$PUBLISHER_SLUG" <<'PY'
import json
import sys
from pathlib import Path

meta_path = Path(sys.argv[1])
src_name = sys.argv[2]
name = sys.argv[3]
publisher = sys.argv[4]
meta = json.loads(meta_path.read_text(encoding='utf-8'))
meta['name'] = name
summary = meta.get('summary')
if isinstance(summary, str) and src_name in summary:
    meta['summary'] = summary.replace(src_name, name)
if publisher:
    meta['publisher'] = publisher
    meta['qualified_name'] = f'{publisher}/{name}'
else:
    meta.pop('publisher', None)
    meta.pop('qualified_name', None)
owners = meta.get('owners')
if not isinstance(owners, list) or not any(isinstance(item, str) and item.strip() for item in owners):
    owner = meta.get('owner')
    meta['owners'] = [owner] if isinstance(owner, str) and owner.strip() else []
author = meta.get('author')
if not isinstance(author, str) or not author.strip():
    owners = [item for item in meta.get('owners', []) if isinstance(item, str) and item.strip()]
    meta['author'] = owners[0] if owners else meta.get('owner')
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
fi

echo "created: $DEST"
