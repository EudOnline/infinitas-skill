#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_MANIFEST_REL = Path('catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json')
TRUST_CONFIG_REFS = [
    Path('config/signing.json'),
    Path('config/allowed_signers'),
]

sys.path.insert(0, str(ROOT / 'scripts'))
from distribution_lib import manifest_index_entry  # noqa: E402


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
    refs.extend(TRUST_CONFIG_REFS)
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


def run_backfill_scan(root: Path, *, write=False):
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'backfill-distribution-manifests.py'),
        '--root',
        str(root),
    ]
    if write:
        command.append('--write')
    command.append('--json')
    result = run(command, cwd=ROOT)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f'backfill scan command did not emit JSON:\n{result.stdout}\n{result.stderr}\n{exc}')


def _status_by_manifest(payload):
    records = payload.get('results')
    if not isinstance(records, list):
        fail(f'expected backfill scan payload to include list results, got {payload!r}')
    status_by_manifest = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        manifest = item.get('manifest')
        if isinstance(manifest, str):
            status_by_manifest[manifest] = item
    return status_by_manifest


def scenario_legacy_manifest_backfill_is_additive_and_idempotent():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-legacy-backfill-test-'))
    try:
        manifest_path, original = copy_legacy_fixture(tmpdir)
        before = load_json(manifest_path)
        if before.get('file_manifest') is not None or before.get('build') is not None:
            fail('expected legacy fixture to start without file_manifest/build fields')

        legacy_index = manifest_index_entry(manifest_path, tmpdir)
        if legacy_index.get('installed_integrity_capability') != 'unknown':
            fail(
                "expected legacy manifest index to report installed_integrity_capability 'unknown', "
                f"got {legacy_index.get('installed_integrity_capability')!r}"
            )
        if legacy_index.get('installed_integrity_reason') != 'missing-signed-file-manifest':
            fail(
                "expected legacy manifest index to report installed_integrity_reason 'missing-signed-file-manifest', "
                f"got {legacy_index.get('installed_integrity_reason')!r}"
            )

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

        rewritten_index = manifest_index_entry(manifest_path, tmpdir)
        if rewritten_index.get('installed_integrity_capability') != 'supported':
            fail(
                "expected rewritten manifest index to report installed_integrity_capability 'supported', "
                f"got {rewritten_index.get('installed_integrity_capability')!r}"
            )
        if rewritten_index.get('installed_integrity_reason') is not None:
            fail(
                'expected rewritten manifest index not to include installed_integrity_reason, '
                f"got {rewritten_index.get('installed_integrity_reason')!r}"
            )
        if rewritten_index.get('file_manifest_count') != len(file_manifest):
            fail(
                f"expected file_manifest_count {len(file_manifest)!r}, got {rewritten_index.get('file_manifest_count')!r}"
            )

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


def scenario_scan_mode_reports_machine_readable_status_per_manifest():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-legacy-backfill-scan-test-'))
    try:
        manifest_path, _ = copy_legacy_fixture(tmpdir)
        broken_manifest_path = tmpdir / 'catalog/distributions/lvxiaoer/operate-infinitas-skill-broken/0.1.1/manifest.json'
        broken_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        broken_payload = load_json(manifest_path)
        broken_payload['bundle'] = {**(broken_payload.get('bundle') or {}), 'path': 'catalog/distributions/missing/skill.tar.gz'}
        broken_manifest_path.write_text(json.dumps(broken_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        scan_payload = run_backfill_scan(tmpdir, write=False)
        if scan_payload.get('state') != 'scan':
            fail(f"expected scan payload state 'scan', got {scan_payload.get('state')!r}")
        if scan_payload.get('inspected_count') != 2:
            fail(f"expected inspected_count=2, got {scan_payload.get('inspected_count')!r}")

        by_manifest = _status_by_manifest(scan_payload)
        canonical_manifest = str(manifest_path.resolve())
        broken_manifest = str(broken_manifest_path.resolve())
        if canonical_manifest not in by_manifest:
            fail(f'expected scan results to include canonical fixture manifest, got {by_manifest!r}')
        if broken_manifest not in by_manifest:
            fail(f'expected scan results to include broken fixture manifest, got {by_manifest!r}')

        canonical_status = by_manifest[canonical_manifest]
        if canonical_status.get('state') != 'would-backfill':
            fail(f"expected canonical scan state 'would-backfill', got {canonical_status!r}")
        if canonical_status.get('installed_integrity_capability') != 'unknown':
            fail(f"expected canonical installed_integrity_capability 'unknown', got {canonical_status!r}")
        if canonical_status.get('installed_integrity_reason') != 'missing-signed-file-manifest':
            fail(f"expected canonical installed_integrity_reason 'missing-signed-file-manifest', got {canonical_status!r}")

        broken_status = by_manifest[broken_manifest]
        if broken_status.get('state') != 'incomplete-evidence':
            fail(f"expected broken scan state 'incomplete-evidence', got {broken_status!r}")
        if broken_status.get('installed_integrity_capability') != 'unknown':
            fail(f"expected broken installed_integrity_capability 'unknown', got {broken_status!r}")
        if broken_status.get('installed_integrity_reason') != 'missing-signed-file-manifest':
            fail(f"expected broken installed_integrity_reason 'missing-signed-file-manifest', got {broken_status!r}")

        write_payload = run_backfill_scan(tmpdir, write=True)
        by_manifest_write = _status_by_manifest(write_payload)
        canonical_write = by_manifest_write.get(canonical_manifest)
        if canonical_write is None or canonical_write.get('state') != 'backfilled':
            fail(f"expected canonical manifest write state 'backfilled', got {canonical_write!r}")
        if canonical_write.get('installed_integrity_capability') != 'supported':
            fail(f"expected canonical write capability 'supported', got {canonical_write!r}")
        if canonical_write.get('file_manifest_count', 0) < 1:
            fail(f"expected canonical write file_manifest_count to be positive, got {canonical_write!r}")

        broken_write = by_manifest_write.get(broken_manifest)
        if broken_write is None or broken_write.get('state') != 'incomplete-evidence':
            fail(f"expected broken write state 'incomplete-evidence', got {broken_write!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_scan_mode_uses_scanned_repo_trust_config():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-legacy-backfill-trust-root-test-'))
    try:
        manifest_path, _ = copy_legacy_fixture(tmpdir)
        broken_manifest_path = tmpdir / 'catalog/distributions/lvxiaoer/operate-infinitas-skill-broken/0.1.1/manifest.json'
        broken_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        broken_payload = load_json(manifest_path)
        broken_payload['bundle'] = {**(broken_payload.get('bundle') or {}), 'path': 'catalog/distributions/missing/skill.tar.gz'}
        broken_manifest_path.write_text(json.dumps(broken_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (tmpdir / 'config' / 'allowed_signers').write_text('', encoding='utf-8')

        scan_payload = run_backfill_scan(tmpdir, write=False)
        if scan_payload.get('state') != 'scan':
            fail(f"expected scan payload state 'scan', got {scan_payload.get('state')!r}")

        by_manifest = _status_by_manifest(scan_payload)
        canonical_status = by_manifest.get(str(manifest_path.resolve()))
        if canonical_status is None:
            fail(f'expected canonical manifest to be reported, got {by_manifest!r}')
        if canonical_status.get('state') != 'incomplete-evidence':
            fail(
                "expected canonical scan state 'incomplete-evidence' when scanned repo has no trusted signers, "
                f'got {canonical_status!r}'
            )
        if 'has no signer entries' not in (canonical_status.get('error') or ''):
            fail(f"expected canonical scan error to mention missing trusted signers, got {canonical_status!r}")
        if canonical_status.get('root') != str(tmpdir.resolve()):
            fail(f"expected canonical scan root {tmpdir.resolve()!s}, got {canonical_status.get('root')!r}")
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
    scenario_scan_mode_reports_machine_readable_status_per_manifest()
    scenario_scan_mode_uses_scanned_repo_trust_config()
    scenario_placeholder_metadata_is_backfillable_and_dry_run_is_non_mutating()
    print('OK: legacy distribution manifest backfill checks passed')


if __name__ == '__main__':
    main()
