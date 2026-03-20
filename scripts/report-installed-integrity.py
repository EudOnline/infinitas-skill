#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from install_integrity_policy_lib import load_install_integrity_policy
from install_manifest_lib import load_install_manifest, write_install_manifest
from installed_integrity_lib import (
    apply_integrity_history_retention,
    append_integrity_event,
    build_install_integrity_snapshot,
    build_installed_integrity_report_item,
    normalize_integrity_events,
    write_installed_integrity_snapshot,
)
from release_lib import ROOT


def parse_args():
    parser = argparse.ArgumentParser(description='Report local installed-skill integrity state from the install manifest')
    parser.add_argument('target_dir', help='Installed skills target directory')
    parser.add_argument('--refresh', action='store_true', help='Re-run local integrity verification and persist refreshed summary fields')
    parser.add_argument('--json', action='store_true', help='Print machine-readable report payload')
    return parser.parse_args()


def _refresh_manifest_entry(target_dir: Path, name: str, item, *, refreshed_at: str):
    updated = dict(item or {})
    installed_name = updated.get('name') or name
    installed_dir = target_dir / installed_name
    snapshot = build_install_integrity_snapshot(
        installed_dir,
        updated,
        root=ROOT,
        verified_at=refreshed_at,
    )
    updated['integrity'] = snapshot['integrity']
    updated['integrity_capability'] = snapshot['integrity_capability']
    updated['integrity_reason'] = snapshot['integrity_reason']
    updated['integrity_events'] = append_integrity_event(
        normalize_integrity_events(updated.get('integrity_events')),
        at=refreshed_at,
        event=(updated.get('integrity') or {}).get('state') or 'unknown',
        source='refresh',
        reason=updated.get('integrity_reason'),
    )
    updated['last_checked_at'] = refreshed_at
    updated['updated_at'] = refreshed_at
    return updated


def _report_payload(target_dir: Path, manifest, *, refreshed: bool, policy):
    skills = []
    for name, item in sorted((manifest.get('skills') or {}).items()):
        if not isinstance(item, dict):
            continue
        skills.append(build_installed_integrity_report_item(name, item, policy=policy))
    return {
        'target_dir': str(target_dir),
        'refreshed': refreshed,
        'skill_count': len(skills),
        'skills': skills,
    }


def main():
    args = parse_args()
    target_dir = Path(args.target_dir).resolve()
    manifest = load_install_manifest(target_dir)
    policy = load_install_integrity_policy(ROOT)

    if args.refresh:
        refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        updated_manifest = dict(manifest)
        skills = updated_manifest.get('skills') or {}
        updated_skills = {}
        for name, item in skills.items():
            updated_skills[name] = _refresh_manifest_entry(target_dir, name, item, refreshed_at=refreshed_at)
        updated_manifest['skills'] = updated_skills
        updated_manifest['updated_at'] = refreshed_at
        updated_manifest, archived_by_name = apply_integrity_history_retention(
            updated_manifest,
            target_dir=target_dir,
            policy=policy,
        )
        write_install_manifest(target_dir, updated_manifest, repo=updated_manifest.get('repo'))
        write_installed_integrity_snapshot(
            target_dir,
            updated_manifest,
            policy=policy,
            archived_by_name=archived_by_name,
            generated_at=refreshed_at,
        )
        manifest = load_install_manifest(target_dir)

    payload = _report_payload(target_dir, manifest, refreshed=args.refresh, policy=policy)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"target: {payload.get('target_dir')}")
        for item in payload.get('skills') or []:
            print(
                f"- {item.get('qualified_name')}@{item.get('installed_version')} "
                f"state={((item.get('integrity') or {}).get('state'))} "
                f"capability={item.get('integrity_capability')} "
                f"action={item.get('recommended_action')}"
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
