#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  echo "usage: scripts/check-skill.sh <skill-dir>" >&2
  exit 1
fi

[[ -d "$DIR" ]] || { echo "missing directory: $DIR" >&2; exit 1; }
[[ -f "$DIR/SKILL.md" ]] || { echo "missing SKILL.md in $DIR" >&2; exit 1; }
[[ -f "$DIR/_meta.json" ]] || { echo "missing _meta.json in $DIR" >&2; exit 1; }

STATUS=0
BASENAME="$(basename "$DIR")"
PARENT_STAGE="$(basename "$(dirname "$DIR")")"
NAME_LINE="$(sed -n 's/^name: //p' "$DIR/SKILL.md" | head -n 1)"
DESC_LINE="$(sed -n 's/^description: //p' "$DIR/SKILL.md" | head -n 1)"

if [[ -z "$NAME_LINE" ]]; then
  echo "FAIL: missing name field in SKILL.md" >&2
  STATUS=1
fi
if [[ -z "$DESC_LINE" ]]; then
  echo "FAIL: missing description field in SKILL.md" >&2
  STATUS=1
fi
if [[ -n "$NAME_LINE" && "$NAME_LINE" != "$BASENAME" ]]; then
  echo "WARN: folder name ($BASENAME) does not match SKILL.md name field ($NAME_LINE)" >&2
fi

if ! python3 - "$DIR" "$BASENAME" "$PARENT_STAGE" "$NAME_LINE" <<'PY'
import json, os, re, sys
path, basename, parent_stage, skill_name = sys.argv[1:5]
meta_path = os.path.join(path, '_meta.json')
status = 0

with open(meta_path, 'r', encoding='utf-8') as f:
    try:
        meta = json.load(f)
    except Exception as e:
        print(f'FAIL: invalid JSON in _meta.json: {e}', file=sys.stderr)
        sys.exit(1)

required = ['name', 'version', 'status', 'summary', 'owner', 'review_state', 'risk_level', 'distribution']
for key in required:
    if key not in meta:
        print(f'FAIL: _meta.json missing required field: {key}', file=sys.stderr)
        status = 1

name = meta.get('name')
if name and name != basename:
    print(f'FAIL: _meta.json name ({name}) does not match folder name ({basename})', file=sys.stderr)
    status = 1
if skill_name and name and skill_name != name:
    print(f'FAIL: SKILL.md name ({skill_name}) does not match _meta.json name ({name})', file=sys.stderr)
    status = 1

version = meta.get('version')
if version and not re.match(r'^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$', version):
    print(f'FAIL: version is not semver-like: {version}', file=sys.stderr)
    status = 1

allowed_status = {'incubating', 'active', 'archived'}
meta_status = meta.get('status')
if meta_status and meta_status not in allowed_status:
    print(f'FAIL: invalid status: {meta_status}', file=sys.stderr)
    status = 1
if meta_status and meta_status != parent_stage:
    print(f'FAIL: _meta.json status ({meta_status}) does not match parent dir ({parent_stage})', file=sys.stderr)
    status = 1

review_state = meta.get('review_state')
if review_state and review_state not in {'draft', 'under-review', 'approved', 'rejected'}:
    print(f'FAIL: invalid review_state: {review_state}', file=sys.stderr)
    status = 1

risk_level = meta.get('risk_level')
if risk_level and risk_level not in {'low', 'medium', 'high'}:
    print(f'FAIL: invalid risk_level: {risk_level}', file=sys.stderr)
    status = 1

distribution = meta.get('distribution')
if distribution is not None and not isinstance(distribution, dict):
    print('FAIL: distribution must be an object', file=sys.stderr)
    status = 1

smoke = meta.get('tests', {}).get('smoke', 'tests/smoke.md')
smoke_path = os.path.join(path, smoke)
if not os.path.isfile(smoke_path):
    print(f'FAIL: missing smoke test file: {smoke}', file=sys.stderr)
    status = 1

derived = meta.get('derived_from')
if derived is not None and derived != '' and not isinstance(derived, str):
    print('FAIL: derived_from must be null or string', file=sys.stderr)
    status = 1

sys.exit(status)
PY
then
  STATUS=1
fi

if grep -RInE '(gh[pousr]_|github_pat_|sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-|-----BEGIN (RSA|OPENSSH|EC|DSA|PGP|PRIVATE KEY)|Authorization:[[:space:]]*Bearer[[:space:]]+[A-Za-z0-9._-]+)' "$DIR" >/tmp/skill-check-secrets.$$ 2>/dev/null; then
  echo "FAIL: possible secrets detected" >&2
  sed -n '1,20p' /tmp/skill-check-secrets.$$ >&2
  STATUS=1
fi
rm -f /tmp/skill-check-secrets.$$

if [[ $STATUS -eq 0 ]]; then
  echo "OK: $DIR"
fi
exit $STATUS
