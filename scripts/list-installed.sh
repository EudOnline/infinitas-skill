#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-$HOME/.openclaw/skills}"
MANIFEST="$TARGET_DIR/.infinitas-skill-install-manifest.json"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ -f "$MANIFEST" ]] || { echo "missing manifest: $MANIFEST" >&2; exit 1; }
python3 - "$ROOT" "$MANIFEST" <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(sys.argv[1], 'scripts'))
from install_integrity_policy_lib import load_install_integrity_policy
from install_manifest_lib import InstallManifestError, load_install_manifest
from installed_integrity_lib import build_integrity_freshness

manifest_path = sys.argv[2]
root = Path(sys.argv[1]).resolve()
try:
    data = load_install_manifest(manifest_path)
except InstallManifestError as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)
policy = load_install_integrity_policy(root)

print(f"repo: {data.get('repo')}")
print(f"updated_at: {data.get('updated_at')}")
for name, meta in sorted(data.get('skills', {}).items()):
    display = meta.get('qualified_name') or meta.get('name') or name
    version = meta.get('version')
    locked = meta.get('locked_version')
    stage = meta.get('source_stage')
    src_type = meta.get('source_type') or 'working-tree'
    src = meta.get('source_distribution_manifest') or meta.get('source_relative_path') or meta.get('source_path')
    registry = meta.get('source_registry') or 'self'
    commit = meta.get('source_snapshot_commit') or meta.get('source_commit')
    tag = meta.get('source_snapshot_tag') or meta.get('source_tag')
    ref = meta.get('source_snapshot_ref') or meta.get('source_ref')
    history_len = len((data.get('history') or {}).get(name) or [])
    resolution_plan = meta.get('resolution_plan') or {}
    resolution_steps = len((resolution_plan.get('steps') or [])) if isinstance(resolution_plan, dict) else 0
    checked_at = meta.get('last_checked_at')
    integrity = meta.get('integrity') or {}
    integrity_state = integrity.get('state') or 'unknown'
    integrity_capability = meta.get('integrity_capability') or 'unknown'
    integrity_events = meta.get('integrity_events') or []
    freshness = build_integrity_freshness(meta, policy=policy)
    lock_note = f", locked={locked}" if locked else ""
    hist_note = f", history={history_len}" if history_len else ""
    plan_note = f", plan_steps={resolution_steps}" if resolution_steps else ""
    checked_note = f", checked={checked_at}" if checked_at else ""
    integrity_note = f", integrity={integrity_state}"
    capability_note = f", capability={integrity_capability}"
    events_note = f", events={len(integrity_events)}"
    freshness_note = f", freshness={freshness.get('freshness_state')}"
    source_note = f"{registry}/{src_type}"
    if commit:
        source_note += f"@{commit[:12]}"
    if tag:
        source_note += f" tag={tag}"
    elif ref:
        source_note += f" ref={ref}"
    print(f"- {display}: {version}{lock_note} [{stage}] ({meta.get('action')}) -> {meta.get('target_path')} from {source_note}:{src}{hist_note}{plan_note}{checked_note}{integrity_note}{capability_note}{freshness_note}{events_note}")
PY
