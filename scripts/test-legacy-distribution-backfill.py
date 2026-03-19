#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_MANIFEST_REL = Path('catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json')


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def copy_legacy_fixture(tmp_root: Path):
    source_manifest = ROOT / LEGACY_MANIFEST_REL
    if not source_manifest.exists():
        fail(f'missing legacy fixture manifest: {source_manifest}')
    original = load_json(source_manifest)
    refs = [
        LEGACY_MANIFEST_REL,
        Path((original.get('bundle') or {}).get('path') or ''),
        Path((original.get('attestation_bundle') or {}).get('provenance_path') or ''),
        Path((original.get('attestation_bundle') or {}).get('signature_path') or ''),
    ]
    if any(not str(ref) for ref in refs):
        fail(f'legacy fixture manifest is missing immutable refs: {original!r}')
    for rel in refs:
        src = ROOT / rel
        dst = tmp_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_root / LEGACY_MANIFEST_REL, original


def run_backfill(manifest_path: Path, *, write=True):
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'backfill-distribution-manifests.py'),
        '--manifest',
        str(manifest_path),
    ]
    if write:
        command.append('--write')
    command.append('--json')
    result = run(
        command,
        cwd=ROOT,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f'backfill command did not emit JSON:\n{result.stdout}\n{result.stderr}\n{exc}')


def scenario_legacy_manifest_backfill_is_additive_and_idempotent():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-legacy-backfill-test-'))
    try:
        manifest_path, original = copy_legacy_fixture(tmpdir)
        before = load_json(manifest_path)
        if before.get('file_manifest') is not None or before.get('build') is not None:
            fail('expected legacy fixture to start without file_manifest/build fields')

        first = run_backfill(manifest_path)
        if first.get('state') != 'backfilled':
            fail(f"expected first backfill pass state 'backfilled', got {first.get('state')!r}")

        rewritten = load_json(manifest_path)
        file_manifest = rewritten.get('file_manifest')
        if not isinstance(file_manifest, list) or not file_manifest:
            fail(f'expected rewritten manifest to include non-empty file_manifest, got {file_manifest!r}')
        build = rewritten.get('build')
        if not isinstance(build, dict) or build.get('archive_format') != 'tar.gz':
            fail(f'expected rewritten manifest to include normalized build metadata, got {build!r}')

        immutable_checks = [
            ('bundle.path', (rewritten.get('bundle') or {}).get('path'), (original.get('bundle') or {}).get('path')),
            ('bundle.sha256', (rewritten.get('bundle') or {}).get('sha256'), (original.get('bundle') or {}).get('sha256')),
            (
                'attestation_bundle.provenance_path',
                (rewritten.get('attestation_bundle') or {}).get('provenance_path'),
                (original.get('attestation_bundle') or {}).get('provenance_path'),
            ),
            (
                'attestation_bundle.signature_path',
                (rewritten.get('attestation_bundle') or {}).get('signature_path'),
                (original.get('attestation_bundle') or {}).get('signature_path'),
            ),
            (
                'attestation_bundle.provenance_sha256',
                (rewritten.get('attestation_bundle') or {}).get('provenance_sha256'),
                (original.get('attestation_bundle') or {}).get('provenance_sha256'),
            ),
            (
                'attestation_bundle.signature_sha256',
                (rewritten.get('attestation_bundle') or {}).get('signature_sha256'),
                (original.get('attestation_bundle') or {}).get('signature_sha256'),
            ),
            ('source_snapshot', rewritten.get('source_snapshot'), original.get('source_snapshot')),
        ]
        for label, actual, expected in immutable_checks:
            if actual != expected:
                fail(f'expected {label} to stay unchanged\nactual: {actual!r}\nexpected: {expected!r}')

        rewritten_text = manifest_path.read_text(encoding='utf-8')
        second = run_backfill(manifest_path)
        if second.get('state') != 'unchanged':
            fail(f"expected second backfill pass state 'unchanged', got {second.get('state')!r}")
        if manifest_path.read_text(encoding='utf-8') != rewritten_text:
            fail('expected unchanged backfill pass not to rewrite manifest bytes')
    finally:
        shutil.rmtree(tmpdir)


def scenario_placeholder_metadata_is_backfillable_and_dry_run_is_non_mutating():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-legacy-backfill-placeholder-test-'))
    try:
        manifest_path, _original = copy_legacy_fixture(tmpdir)
        payload = load_json(manifest_path)
        payload['file_manifest'] = []
        payload['build'] = {}
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        before_text = manifest_path.read_text(encoding='utf-8')

        dry_run = run_backfill(manifest_path, write=False)
        if dry_run.get('state') != 'would-backfill':
            fail(f"expected dry-run state 'would-backfill', got {dry_run.get('state')!r}")
        if dry_run.get('wrote') is not False:
            fail(f"expected dry-run wrote=false, got {dry_run.get('wrote')!r}")
        if manifest_path.read_text(encoding='utf-8') != before_text:
            fail('expected dry-run backfill not to mutate manifest bytes')

        applied = run_backfill(manifest_path, write=True)
        if applied.get('state') != 'backfilled':
            fail(f"expected write pass state 'backfilled', got {applied.get('state')!r}")
        rewritten = load_json(manifest_path)
        if not isinstance(rewritten.get('file_manifest'), list) or not rewritten.get('file_manifest'):
            fail(f"expected file_manifest list to be backfilled from placeholders, got {rewritten.get('file_manifest')!r}")
        build = rewritten.get('build')
        if not isinstance(build, dict) or build.get('archive_format') != 'tar.gz':
            fail(f"expected build object to be backfilled from placeholders, got {build!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_legacy_manifest_backfill_is_additive_and_idempotent()
    scenario_placeholder_metadata_is_backfillable_and_dry_run_is_non_mutating()
    print('OK: legacy distribution manifest backfill checks passed')


if __name__ == '__main__':
    main()
