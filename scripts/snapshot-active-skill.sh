#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "usage: scripts/snapshot-active-skill.sh <skill-name> [--label TEXT]" >&2
  exit 1
fi
shift || true
LABEL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --label)
      LABEL="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/skills/active/$NAME"
[[ -d "$SRC" ]] || { echo "missing active skill: $NAME" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$SRC" >/dev/null

readarray -t META < <(python3 - "$SRC/_meta.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(meta['name'])
print(meta['version'])
PY
)
SKILL_NAME="${META[0]}"
VERSION="${META[1]}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SAFE_LABEL=""
if [[ -n "$LABEL" ]]; then
  SAFE_LABEL="-$(printf '%s' "$LABEL" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-_')"
fi
DEST="$ROOT/skills/archived/${SKILL_NAME}--v${VERSION}--${STAMP}${SAFE_LABEL}"
[[ ! -e "$DEST" ]] || { echo "snapshot already exists: $DEST" >&2; exit 1; }
cp -R "$SRC" "$DEST"
python3 - "$DEST/_meta.json" "$SKILL_NAME" "$VERSION" "$STAMP" "$LABEL" <<'PY'
import json, sys
p, source_name, source_version, stamp, label = sys.argv[1:6]
with open(p, 'r', encoding='utf-8') as f:
    meta = json.load(f)
meta['status'] = 'archived'
meta['snapshot_of'] = f'{source_name}@{source_version}'
meta['snapshot_created_at'] = stamp
if label:
    meta['snapshot_label'] = label
with open(p, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
    f.write('\n')
PY
"$ROOT/scripts/build-catalog.sh" >/dev/null
echo "snapshot: $DEST"
