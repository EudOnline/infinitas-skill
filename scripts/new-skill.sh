#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-}"
TEMPLATE="${2:-basic}"
TARGET_ROOT="${3:-skills/incubating}"

if [[ -z "$NAME" ]]; then
  echo "usage: scripts/new-skill.sh <skill-name> [basic|scripted|reference-heavy] [target-root]" >&2
  exit 1
fi

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g'
}

SLUG="$(slugify "$NAME")"
[[ -n "$SLUG" ]] || { echo "invalid skill name" >&2; exit 1; }

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
  sed -i "s/$SRC_NAME/$SLUG/g" "$DEST/_meta.json"
fi

echo "created: $DEST"
