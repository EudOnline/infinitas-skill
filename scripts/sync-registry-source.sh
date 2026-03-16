#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/sync-registry-source.sh <registry-name> [--force] [--snapshot ID|latest]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$1"
shift || true
FORCE=0
SNAPSHOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --snapshot)
      SNAPSHOT="${2:-}"
      [[ -n "$SNAPSHOT" ]] || { echo "missing value for --snapshot" >&2; exit 1; }
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

python3 - "$ROOT" "$NAME" "$FORCE" "$SNAPSHOT" <<'PY'
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
name = sys.argv[2]
force = sys.argv[3] == '1'
snapshot_selector = sys.argv[4].strip() if len(sys.argv) > 4 else ''
sys.path.insert(0, str(root / 'scripts'))

from registry_snapshot_lib import resolve_snapshot_selector  # noqa: E402
from registry_source_lib import (  # noqa: E402
    canonical_pin_ref,
    extract_git_host,
    find_registry,
    load_registry_config,
    normalized_allowed_hosts,
    normalized_allowed_refs,
    normalized_pin,
    normalized_update_policy,
    resolve_registry_root,
    short_pin_value,
    validate_registry_config,
)
from registry_refresh_state_lib import write_refresh_state  # noqa: E402


def fail(message):
    raise SystemExit(message)


def git(*args):
    subprocess.check_call(['git', *args])


def git_capture(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def is_cache_path(path):
    cache_root = (root / '.cache' / 'registries').resolve()
    try:
        path.resolve().relative_to(cache_root)
        return True
    except Exception:
        return False


cfg = load_registry_config(root)
errors = validate_registry_config(root, cfg)
if errors:
    fail('invalid registry-sources.json:\n- ' + '\n- '.join(errors))

reg = find_registry(cfg, name)
if not reg:
    fail(f'unknown registry: {name}')
if not reg.get('enabled', True):
    fail(f'registry is disabled: {name}')

if snapshot_selector:
    snapshot_record = resolve_snapshot_selector(root, name, snapshot_selector)
    if snapshot_record is None:
        fail(f"snapshot '{snapshot_selector}' not found for registry '{name}'")
    summary = snapshot_record.get('summary') or {}
    snapshot_root = summary.get('snapshot_root')
    if not isinstance(snapshot_root, str) or not snapshot_root.strip():
        fail(f"snapshot '{summary.get('snapshot_id') or snapshot_selector}' for registry '{name}' is missing snapshot_root metadata")
    resolved_snapshot_root = Path(snapshot_root)
    if not resolved_snapshot_root.is_absolute():
        resolved_snapshot_root = (root / resolved_snapshot_root).resolve()
    else:
        resolved_snapshot_root = resolved_snapshot_root.resolve()
    if not resolved_snapshot_root.exists():
        fail(f"snapshot '{summary.get('snapshot_id') or snapshot_selector}' for registry '{name}' is missing its registry tree")
    print(resolved_snapshot_root)
    raise SystemExit(0)

kind = reg.get('kind')
p = resolve_registry_root(root, reg)
pin = normalized_pin(reg)
update_policy = normalized_update_policy(reg)
allowed_hosts = normalized_allowed_hosts(reg)
allowed_refs = normalized_allowed_refs(reg)
desired_ref = canonical_pin_ref(pin.get('mode'), pin.get('value'))
configured_host = extract_git_host(reg.get('url'))

if kind == 'local':
    if not p or not p.exists():
        fail(f'local registry path does not exist: {p}')
    print(p)
    raise SystemExit(0)

if kind != 'git':
    fail(f'unsupported registry kind: {kind}')

if configured_host and configured_host not in allowed_hosts:
    fail(f'registry {name} url host {configured_host!r} is not allowed by policy')

if update_policy.get('mode') == 'local-only':
    if not p or not p.exists():
        fail(f'local-only registry path does not exist: {p}')
    if not (p / '.git').exists():
        fail(f'local-only git registry path is not a git checkout: {p}')
    try:
        origin_url = git_capture(p, 'config', '--get', 'remote.origin.url')
    except Exception:
        origin_url = None
    origin_host = extract_git_host(origin_url)
    if configured_host and origin_host and origin_host != configured_host:
        fail(f'registry {name} origin host {origin_host!r} does not match configured host {configured_host!r}')
    if origin_host and origin_host not in allowed_hosts:
        fail(f'registry {name} origin host {origin_host!r} is not allowed by policy')
    print(p)
    raise SystemExit(0)

if not p:
    fail(f'could not resolve registry root for {name}')
if p == root:
    fail(f'refusing to sync registry {name} into the working repository root; use local-only mode')

if force and p.exists() and is_cache_path(p):
    shutil.rmtree(p)

url = reg.get('url')
if not url:
    fail(f'git registry {name} missing url')

p.parent.mkdir(parents=True, exist_ok=True)
if p.exists() and not (p / '.git').exists():
    fail(f'target cache path exists and is not a git repo: {p}')

if not (p / '.git').exists():
    if p.exists() and any(p.iterdir()):
        fail(f'target cache path exists and is not empty: {p}')
    git('clone', '--no-checkout', url, str(p))

origin_url = git_capture(p, 'config', '--get', 'remote.origin.url')
origin_host = extract_git_host(origin_url)
if configured_host and origin_host and origin_host != configured_host:
    fail(f'registry {name} origin host {origin_host!r} does not match configured host {configured_host!r}')
if origin_host and origin_host not in allowed_hosts:
    fail(f'registry {name} origin host {origin_host!r} is not allowed by policy')

git('-C', str(p), 'fetch', '--prune', '--tags', 'origin')

commit = None
if update_policy.get('mode') == 'track':
    branch = short_pin_value('branch', pin.get('value'))
    if desired_ref not in allowed_refs:
        fail(f'registry {name} desired ref {desired_ref!r} is not allowed by policy')
    git('-C', str(p), 'fetch', '--prune', 'origin', f'+{desired_ref}:refs/remotes/origin/{branch}')
    try:
        commit = git_capture(p, 'rev-parse', f'refs/remotes/origin/{branch}')
    except Exception as exc:
        fail(f'registry {name} could not resolve remote branch {branch!r}: {exc}')
elif update_policy.get('mode') == 'pinned':
    if pin.get('mode') == 'tag':
        tag = short_pin_value('tag', pin.get('value'))
        if desired_ref not in allowed_refs:
            fail(f'registry {name} desired ref {desired_ref!r} is not allowed by policy')
        try:
            commit = git_capture(p, 'rev-parse', f'refs/tags/{tag}^{{commit}}')
        except Exception as exc:
            fail(f'registry {name} pinned tag {tag!r} is not available after fetch: {exc}')
    elif pin.get('mode') == 'commit':
        commit = pin.get('value')
        try:
            git_capture(p, 'rev-parse', f'{commit}^{{commit}}')
        except Exception:
            try:
                git('-C', str(p), 'fetch', 'origin', commit)
                git_capture(p, 'rev-parse', f'{commit}^{{commit}}')
            except Exception as exc:
                fail(f'registry {name} pinned commit {commit!r} is not available after fetch: {exc}')
    else:
        fail(f'registry {name} pinned policy requires tag or commit pinning')
else:
    fail(f'registry {name} unsupported update policy: {update_policy.get("mode")}')

git('-C', str(p), 'checkout', '--detach', commit)
git('-C', str(p), 'reset', '--hard', commit)
write_refresh_state(
    root,
    registry_name=name,
    kind=kind,
    cache_path=p,
    source_commit=commit,
    source_ref=desired_ref,
    source_tag=short_pin_value('tag', pin.get('value')) if pin.get('mode') == 'tag' else None,
)
print(p)
PY
