#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/release-skill.sh <skill-name-or-path> [--create-tag] [--push-tag] [--github-release] [--notes-out PATH] [--write-provenance]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
CREATE_TAG=0
PUSH_TAG=0
GITHUB_RELEASE=0
NOTES_OUT=""
WRITE_PROVENANCE=0

resolve_skill() {
  local name="$1"
  if [[ -d "$name" && -f "$name/_meta.json" ]]; then
    printf '%s' "$name"
    return
  fi
  for stage in active incubating archived; do
    if [[ -d "$ROOT/skills/$stage/$name" ]]; then
      printf '%s' "$ROOT/skills/$stage/$name"
      return
    fi
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --create-tag)
      CREATE_TAG=1
      shift
      ;;
    --push-tag)
      PUSH_TAG=1
      CREATE_TAG=1
      shift
      ;;
    --github-release)
      GITHUB_RELEASE=1
      CREATE_TAG=1
      shift
      ;;
    --notes-out)
      NOTES_OUT="${2:-}"
      shift 2
      ;;
    --write-provenance)
      WRITE_PROVENANCE=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$DIR" >/dev/null
"$ROOT/scripts/check-all.sh" >/dev/null

META_JSON="$(mktemp)"
python3 - "$DIR" "$META_JSON" <<'PY'
import json, re, sys
from pathlib import Path
skill_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
name = meta['name']
version = meta['version']
status = meta.get('status')
changelog = (skill_dir / 'CHANGELOG.md').read_text(encoding='utf-8')
pattern = re.compile(rf'^##\s+{re.escape(version)}\s+-.*?(?=^##\s+|\Z)', re.M | re.S)
m = pattern.search(changelog)
notes = m.group(0).strip() if m else f'## {version}\n\n- No matching changelog section found.'
out.write_text(json.dumps({
    'name': name,
    'version': version,
    'status': status,
    'notes': notes,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

NAME="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['name'])
PY
)"
VERSION="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['version'])
PY
)"
STATUS="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['status'])
PY
)"
TAG="skill/$NAME/v$VERSION"

if [[ "$STATUS" != "active" ]]; then
  rm -f "$META_JSON"
  echo "release-skill.sh expects an active skill; current status is $STATUS" >&2
  exit 1
fi

if [[ -n "$NOTES_OUT" ]]; then
  python3 - <<'PY' "$META_JSON" "$NOTES_OUT"
import json, sys
notes = json.load(open(sys.argv[1], encoding='utf-8'))['notes']
open(sys.argv[2], 'w', encoding='utf-8').write(notes + '\n')
PY
fi

echo "skill: $NAME"
echo "version: $VERSION"
echo "status: $STATUS"
echo "tag: $TAG"
echo
python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['notes'])
PY

if [[ $CREATE_TAG -eq 1 ]]; then
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    rm -f "$META_JSON"
    echo "tag already exists: $TAG" >&2
    exit 1
  fi
  git tag "$TAG"
  echo "created tag: $TAG"
fi

if [[ $PUSH_TAG -eq 1 ]]; then
  git push origin "$TAG"
fi

if [[ $WRITE_PROVENANCE -eq 1 ]]; then
  mkdir -p "$ROOT/catalog/provenance"
  python3 "$ROOT/scripts/generate-provenance.py" "$DIR" > "$ROOT/catalog/provenance/$NAME-$VERSION.json"
  echo "wrote provenance: $ROOT/catalog/provenance/$NAME-$VERSION.json"
fi

if [[ $GITHUB_RELEASE -eq 1 ]]; then
  TMP_NOTES="$(mktemp)"
  python3 - <<'PY' "$META_JSON" "$TMP_NOTES"
import json, sys
open(sys.argv[2], 'w', encoding='utf-8').write(json.load(open(sys.argv[1], encoding='utf-8'))['notes'] + '\n')
PY
  gh release create "$TAG" --title "$TAG" --notes-file "$TMP_NOTES"
  rm -f "$TMP_NOTES"
fi

rm -f "$META_JSON"
