#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/sync-registry-source.sh <registry-name> [--force]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$1"
shift || true
FORCE=0
for arg in "$@"; do
  [[ "$arg" == "--force" ]] && FORCE=1
done

python3 - "$ROOT" "$NAME" "$FORCE" <<'PY'
import json, shutil, subprocess, sys
from pathlib import Path

root = Path(sys.argv[1])
name = sys.argv[2]
force = sys.argv[3] == '1'
cfg = json.loads((root / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))
reg = next((r for r in cfg.get('registries', []) if r.get('name') == name), None)
if not reg:
    raise SystemExit(f'unknown registry: {name}')
kind = reg.get('kind')
local_path = reg.get('local_path')
if local_path:
    p = Path(local_path)
    if not p.is_absolute():
        p = (root / p).resolve()
else:
    p = (root / '.cache' / 'registries' / name).resolve()

if kind == 'local':
    if not p.exists():
        raise SystemExit(f'local registry path does not exist: {p}')
    print(p)
    raise SystemExit(0)

if kind != 'git':
    raise SystemExit(f'unsupported registry kind: {kind}')

url = reg.get('url')
branch = reg.get('branch', 'main')
if not url:
    raise SystemExit(f'git registry {name} missing url')

p.parent.mkdir(parents=True, exist_ok=True)
if p.exists() and force and local_path and Path(local_path).resolve() != p:
    shutil.rmtree(p)

if (p / '.git').exists():
    subprocess.check_call(['git', '-C', str(p), 'fetch', '--prune', 'origin', branch])
    subprocess.check_call(['git', '-C', str(p), 'checkout', '-B', branch, f'origin/{branch}'])
    subprocess.check_call(['git', '-C', str(p), 'reset', '--hard', f'origin/{branch}'])
else:
    if p.exists() and any(p.iterdir()):
        raise SystemExit(f'target cache path exists and is not a git repo: {p}')
    subprocess.check_call(['git', 'clone', '--branch', branch, url, str(p)])

print(p)
PY
