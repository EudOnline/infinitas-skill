#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from compatibility_evidence_lib import normalize_declared_support, write_compatibility_evidence
from release_lib import ROOT, ReleaseError, resolve_skill
from skill_identity_lib import normalize_skill_identity


class VerifiedSupportError(Exception):
    pass


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_args():
    parser = argparse.ArgumentParser(description='Export skills through the real platform adapters, run platform checks, and write compatibility evidence.')
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument('--platform', action='append', dest='platforms', default=[], help='Platform to verify (repeatable): claude, codex, openclaw')
    parser.add_argument('--version', help='Explicit version to verify; defaults to the current skill version')
    parser.add_argument('--build-catalog', action='store_true', help='Rebuild catalog views after writing evidence')
    parser.add_argument('--json', action='store_true', help='Print machine-readable output')
    return parser.parse_args()


def run(command, *, cwd: Path):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f'command failed: {command!r}'
        raise VerifiedSupportError(message)
    return result


def load_skill_state(root: Path, target: str):
    skill_dir = resolve_skill(root, target)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    identity = normalize_skill_identity(meta)
    return skill_dir, meta, identity


def selected_platforms(meta: dict, requested: list[str]) -> list[str]:
    if requested:
        return normalize_declared_support(requested)
    declared = normalize_declared_support(meta.get('agent_compatible') or [])
    return declared or ['codex', 'claude', 'openclaw']


def ensure_version(meta: dict, requested_version: str | None) -> str:
    version = meta.get('version')
    if not isinstance(version, str) or not version:
        raise VerifiedSupportError('skill metadata is missing version')
    if requested_version and requested_version != version:
        raise VerifiedSupportError(f'--version {requested_version!r} does not match skill version {version!r}')
    return version


def evidence_path(root: Path, platform: str, skill_name: str, version: str) -> Path:
    return root / 'catalog' / 'compatibility-evidence' / platform / skill_name / f'{version}.json'


def write_platform_evidence(root: Path, *, platform: str, skill_name: str, qualified_name: str | None, version: str, checker: str, note: str):
    path = evidence_path(root, platform, skill_name, version)
    write_compatibility_evidence(
        path,
        {
            'platform': platform,
            'skill': skill_name,
            'qualified_name': qualified_name,
            'version': version,
            'state': 'adapted',
            'checked_at': utc_now_iso(),
            'checker': checker,
            'note': note,
        },
    )
    return path


def verify_codex(root: Path, skill_dir: Path, skill_name: str, qualified_name: str | None, version: str):
    with tempfile.TemporaryDirectory(prefix=f'infinitas-codex-verify-{skill_name}-') as tmpdir:
        out_dir = Path(tmpdir) / 'codex'
        run([str(root / 'scripts' / 'export-codex-skill.sh'), '--skill-dir', str(skill_dir), '--out', str(out_dir)], cwd=root)
        run([sys.executable, str(root / 'scripts' / 'check-codex-compat.py'), '--skill-dir', str(out_dir)], cwd=root)
        path = write_platform_evidence(
            root,
            platform='codex',
            skill_name=skill_name,
            qualified_name=qualified_name,
            version=version,
            checker='check-codex-compat.py',
            note='Rendered with export-codex-skill.sh and verified with check-codex-compat.py.',
        )
        return {'platform': 'codex', 'export_dir': str(out_dir), 'evidence_path': str(path.relative_to(root)), 'state': 'adapted'}


def verify_claude(root: Path, skill_dir: Path, skill_name: str, qualified_name: str | None, version: str):
    with tempfile.TemporaryDirectory(prefix=f'infinitas-claude-verify-{skill_name}-') as tmpdir:
        out_dir = Path(tmpdir) / 'claude'
        run([str(root / 'scripts' / 'export-claude-skill.sh'), '--skill-dir', str(skill_dir), '--out', str(out_dir)], cwd=root)
        run([sys.executable, str(root / 'scripts' / 'check-claude-compat.py'), '--skill-dir', str(out_dir)], cwd=root)
        path = write_platform_evidence(
            root,
            platform='claude',
            skill_name=skill_name,
            qualified_name=qualified_name,
            version=version,
            checker='check-claude-compat.py',
            note='Rendered with export-claude-skill.sh and verified with check-claude-compat.py.',
        )
        return {'platform': 'claude', 'export_dir': str(out_dir), 'evidence_path': str(path.relative_to(root)), 'state': 'adapted'}


def verify_openclaw(root: Path, skill_name: str, qualified_name: str | None, version: str):
    requested = qualified_name or skill_name
    with tempfile.TemporaryDirectory(prefix=f'infinitas-openclaw-verify-{skill_name}-') as tmpdir:
        export_root = Path(tmpdir) / 'openclaw'
        result = run(
            [
                str(root / 'scripts' / 'export-openclaw-skill.sh'),
                requested,
                '--version',
                version,
                '--out',
                str(export_root),
                '--force',
            ],
            cwd=root,
        )
        payload = json.loads(result.stdout)
        export_dir = Path(payload.get('export_dir') or export_root / skill_name).resolve()
        run([sys.executable, str(root / 'scripts' / 'check-openclaw-compat.py'), '--skill-dir', str(export_dir)], cwd=root)
        path = write_platform_evidence(
            root,
            platform='openclaw',
            skill_name=skill_name,
            qualified_name=qualified_name,
            version=version,
            checker='check-openclaw-compat.py',
            note='Rendered from immutable release artifacts with export-openclaw-skill.sh and verified with check-openclaw-compat.py.',
        )
        return {'platform': 'openclaw', 'export_dir': str(export_dir), 'evidence_path': str(path.relative_to(root)), 'state': 'adapted'}


def main():
    args = parse_args()
    try:
        skill_dir, meta, identity = load_skill_state(ROOT, args.skill)
        skill_name = meta.get('name') or skill_dir.name
        qualified_name = identity.get('qualified_name')
        version = ensure_version(meta, args.version)
        platforms = selected_platforms(meta, args.platforms)
        if not platforms:
            raise VerifiedSupportError('no platforms selected for verification')

        results = []
        for platform in platforms:
            if platform == 'codex':
                results.append(verify_codex(ROOT, skill_dir, skill_name, qualified_name, version))
            elif platform == 'claude':
                results.append(verify_claude(ROOT, skill_dir, skill_name, qualified_name, version))
            elif platform == 'openclaw':
                results.append(verify_openclaw(ROOT, skill_name, qualified_name, version))
            else:
                raise VerifiedSupportError(f'unsupported platform: {platform}')

        if args.build_catalog:
            run([str(ROOT / 'scripts' / 'build-catalog.sh')], cwd=ROOT)

        payload = {
            'ok': True,
            'skill': skill_name,
            'qualified_name': qualified_name,
            'version': version,
            'platforms': platforms,
            'results': results,
            'catalog_rebuilt': args.build_catalog,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, ensure_ascii=False))
        return 0
    except (VerifiedSupportError, ReleaseError, json.JSONDecodeError) as exc:
        payload = {
            'ok': False,
            'skill': args.skill,
            'platforms': args.platforms,
            'message': str(exc),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
