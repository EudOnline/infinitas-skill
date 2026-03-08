#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/bump-skill-version.sh <skill-name-or-path> [patch|minor|major] [--set X.Y.Z] [--note TEXT ...]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
BUMP_KIND="patch"
SET_VERSION=""
NOTES=()

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

while [[ $# -gt 0 ]]; do
  case "$1" in
    patch|minor|major)
      BUMP_KIND="$1"
      shift
      ;;
    --set)
      SET_VERSION="${2:-}"
      shift 2
      ;;
    --note)
      NOTES+=("${2:-}")
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
python3 - "$DIR" "$BUMP_KIND" "$SET_VERSION" "${NOTES[@]:-}" <<'PY'
import json, re, sys
from datetime import date
from pathlib import Path

skill_dir = Path(sys.argv[1])
bump_kind = sys.argv[2]
set_version = sys.argv[3]
notes = [n for n in sys.argv[4:] if n]
meta_path = skill_dir / '_meta.json'
changelog_path = skill_dir / 'CHANGELOG.md'

with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)
current = meta['version']
match = re.match(r'^(\d+)\.(\d+)\.(\d+)(.*)?$', current)
if not match:
    raise SystemExit(f'invalid current version: {current}')
major, minor, patch = map(int, match.groups()[:3])
suffix = match.group(4) or ''

if set_version:
    new_version = set_version
else:
    if bump_kind == 'major':
        major, minor, patch = major + 1, 0, 0
    elif bump_kind == 'minor':
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new_version = f'{major}.{minor}.{patch}'

meta['version'] = new_version
with open(meta_path, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
    f.write('\n')

entry_lines = [f'## {new_version} - {date.today().isoformat()}', '']
if notes:
    entry_lines.extend([f'- {note}' for note in notes])
else:
    entry_lines.append('- Describe the changes in this release.')
entry = '\n'.join(entry_lines).rstrip() + '\n\n'

if changelog_path.exists():
    existing = changelog_path.read_text(encoding='utf-8')
    if f'## {new_version} - ' not in existing:
        if existing.startswith('# Changelog'):
            parts = existing.split('\n', 2)
            if len(parts) >= 3:
                updated = parts[0] + '\n' + parts[1] + '\n' + entry + parts[2]
            else:
                updated = '# Changelog\n\n' + entry
        else:
            updated = '# Changelog\n\n' + entry + existing
        changelog_path.write_text(updated, encoding='utf-8')
else:
    changelog_path.write_text('# Changelog\n\n' + entry, encoding='utf-8')

print(f'{skill_dir.name}: {current} -> {new_version}')
print(f'updated: {meta_path}')
print(f'updated: {changelog_path}')
PY
