#!/usr/bin/env python3
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = 'operate-infinitas-skill'
PUBLISHER = 'lvxiaoer'
QUALIFIED_NAME = f'{PUBLISHER}/{SKILL_NAME}'
VERSION = '0.1.1'
TRUST_CONFIG_REFS = [
    Path('config/signing.json'),
    Path('config/allowed_signers'),
]


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_current_skill_payload():
    ai_index = json.loads((ROOT / 'catalog' / 'ai-index.json').read_text(encoding='utf-8'))
    distributions = json.loads((ROOT / 'catalog' / 'distributions.json').read_text(encoding='utf-8'))
    skill = next(item for item in ai_index.get('skills', []) if item.get('qualified_name') == QUALIFIED_NAME)
    dist = next(item for item in distributions.get('skills', []) if item.get('qualified_name') == QUALIFIED_NAME and item.get('version') == VERSION)
    return skill, dist


def prepare_served_registry(
    root_dir: Path, *, bundle_sha256=None, installable=True, missing_provenance=False, backfill_manifest=False
):
    skill, dist = load_current_skill_payload()

    manifest_rel = Path(skill['versions'][VERSION]['manifest_path'])
    bundle_rel = Path(skill['versions'][VERSION]['bundle_path'])
    provenance_rel = Path(skill['versions'][VERSION]['attestation_path'])
    signature_rel = Path(skill['versions'][VERSION]['attestation_signature_path'])

    for rel in [manifest_rel, bundle_rel, provenance_rel, signature_rel, *TRUST_CONFIG_REFS]:
        source = ROOT / rel
        target = root_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    if missing_provenance:
        (root_dir / provenance_rel).unlink()

    if backfill_manifest:
        backfill_result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'backfill-distribution-manifests.py'),
                '--manifest',
                str(root_dir / manifest_rel),
                '--write',
                '--json',
            ],
            cwd=ROOT,
        )
        payload = json.loads(backfill_result.stdout)
        if payload.get('state') not in {'backfilled', 'unchanged'}:
            fail(f'expected hosted backfill state backfilled/unchanged, got {payload!r}')

    ai_skill = json.loads(json.dumps(skill))
    ai_skill['default_install_version'] = VERSION
    ai_skill['latest_version'] = VERSION
    ai_skill['available_versions'] = [VERSION]
    ai_skill['versions'] = {
        VERSION: {
            **ai_skill['versions'][VERSION],
            'bundle_sha256': bundle_sha256 or ai_skill['versions'][VERSION]['bundle_sha256'],
            'installable': installable,
        }
    }
    ai_index = {
        'schema_version': 1,
        'generated_at': '2026-03-13T00:00:00Z',
        'registry': {'default_registry': 'hosted'},
        'install_policy': {
            'mode': 'immutable-only',
            'direct_source_install_allowed': False,
            'require_attestation': True,
            'require_sha256': True,
        },
        'skills': [ai_skill],
    }
    write_json(root_dir / 'ai-index.json', ai_index)

    dist_entry = {
        'name': dist.get('name'),
        'publisher': dist.get('publisher'),
        'qualified_name': dist.get('qualified_name'),
        'identity_mode': dist.get('identity_mode'),
        'version': VERSION,
        'status': dist.get('status'),
        'summary': dist.get('summary'),
        'manifest_path': str(manifest_rel),
        'bundle_path': str(bundle_rel),
        'bundle_sha256': bundle_sha256 or dist.get('bundle_sha256'),
        'attestation_path': str(provenance_rel),
        'attestation_signature_path': str(signature_rel),
        'generated_at': '2026-03-13T00:00:00Z',
        'source_type': 'distribution-manifest',
        'source_snapshot_kind': dist.get('source_snapshot_kind'),
        'source_snapshot_tag': dist.get('source_snapshot_tag'),
        'source_snapshot_ref': dist.get('source_snapshot_ref'),
        'source_snapshot_commit': dist.get('source_snapshot_commit'),
    }
    write_json(root_dir / 'distributions.json', {'generated_at': '2026-03-13T00:00:00Z', 'skills': [dist_entry]})
    write_json(root_dir / 'compatibility.json', {'generated_at': '2026-03-13T00:00:00Z', 'skills': []})


def prepare_repo(tmpdir: Path, base_url: str):
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    write_json(
        repo / 'config' / 'registry-sources.json',
        {
            '$schema': '../schemas/registry-sources.schema.json',
            'default_registry': 'hosted',
            'registries': [
                {
                    'name': 'hosted',
                    'kind': 'http',
                    'base_url': base_url,
                    'enabled': True,
                    'priority': 100,
                    'trust': 'untrusted',
                    'auth': {'mode': 'none'},
                    'notes': 'Hosted registry fixture for install tests',
                }
            ],
        },
    )
    return repo


class QuietTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class HostedRegistryServer:
    def __init__(self, directory: Path):
        self.directory = directory
        self.httpd = None
        self.thread = None
        self.base_url = None

    def __enter__(self):
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(self.directory))
        self.httpd = QuietTCPServer(('127.0.0.1', 0), handler)
        port = self.httpd.server_address[1]
        self.base_url = f'http://127.0.0.1:{port}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)


def assert_install_success(repo: Path, target_dir: Path, *, expected_integrity_state: str):
    result = run([str(repo / 'scripts' / 'install-by-name.sh'), SKILL_NAME, str(target_dir)], cwd=repo)
    payload = json.loads(result.stdout)
    if payload.get('state') != 'installed':
        fail(f"expected installed state, got {payload.get('state')!r}")
    manifest_path = Path(payload.get('manifest_path') or '')
    if not manifest_path.exists():
        fail(f'missing install manifest: {manifest_path}')
    installed_skill = target_dir / SKILL_NAME
    if not installed_skill.is_dir():
        fail(f'missing installed skill directory: {installed_skill}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entry = (manifest.get('skills') or {}).get(SKILL_NAME) or {}
    if entry.get('source_registry') != 'hosted':
        fail(f"expected source_registry 'hosted', got {entry.get('source_registry')!r}")
    if entry.get('source_registry_kind') != 'http':
        fail(f"expected source_registry_kind 'http', got {entry.get('source_registry_kind')!r}")
    if not isinstance(entry.get('source_repo'), str) or not entry['source_repo'].startswith('http://127.0.0.1:'):
        fail(f"expected hosted source_repo URL, got {entry.get('source_repo')!r}")
    if entry.get('source_distribution_manifest') != f'catalog/distributions/{PUBLISHER}/{SKILL_NAME}/{VERSION}/manifest.json':
        fail(f"unexpected source_distribution_manifest {entry.get('source_distribution_manifest')!r}")
    if expected_integrity_state == 'verified':
        source_distribution_root = Path(entry.get('source_distribution_root') or '')
        if not source_distribution_root.is_dir():
            fail(f"expected hosted install to persist source_distribution_root, got {entry.get('source_distribution_root')!r}")
        required_cached_refs = [
            entry.get('source_distribution_manifest'),
            entry.get('source_distribution_bundle'),
            entry.get('source_attestation_path'),
            entry.get('source_attestation_signature_path'),
        ]
        for rel in required_cached_refs:
            if not isinstance(rel, str) or not rel:
                fail(f'expected cached hosted install references to be populated, got {required_cached_refs!r}')
            if not (source_distribution_root / rel).exists():
                fail(f'expected cached hosted install artifact to exist: {(source_distribution_root / rel)}')
    integrity = entry.get('integrity')
    if not isinstance(integrity, dict):
        fail(f'expected install manifest integrity block, got {integrity!r}')
    if integrity.get('state') != expected_integrity_state:
        fail(
            f"expected hosted install integrity state {expected_integrity_state!r}, got {integrity.get('state')!r}"
        )
    if expected_integrity_state == 'unknown' and integrity.get('last_verified_at') is not None:
        fail(f"expected hosted install integrity last_verified_at to stay null, got {integrity.get('last_verified_at')!r}")
    if expected_integrity_state == 'verified' and not integrity.get('last_verified_at'):
        fail(f"expected hosted install integrity last_verified_at to be populated, got {integrity.get('last_verified_at')!r}")

    verify_expect = 0 if expected_integrity_state == 'verified' else 1
    verify = run(
        [
            sys.executable,
            str(repo / 'scripts' / 'verify-installed-skill.py'),
            SKILL_NAME,
            str(target_dir),
            '--json',
        ],
        cwd=repo,
        expect=verify_expect,
    )
    verify_payload = json.loads(verify.stdout)
    if expected_integrity_state == 'unknown':
        if verify_payload.get('state') != 'failed':
            fail(f"expected hosted explicit verification failure, got {verify_payload.get('state')!r}")
        error = verify_payload.get('error') or ''
        if 'missing signed file_manifest' not in error:
            fail(f'expected explicit verification to report missing signed file_manifest\n{verify.stdout}\n{verify.stderr}')
    else:
        if verify_payload.get('state') != 'verified':
            fail(f"expected hosted explicit verification success, got {verify_payload.get('state')!r}")


def assert_install_failure(repo: Path, target_dir: Path, needle: str):
    result = run([str(repo / 'scripts' / 'install-by-name.sh'), SKILL_NAME, str(target_dir)], cwd=repo, expect=1)
    combined = result.stdout + result.stderr
    if needle not in combined:
        fail(f'expected failure containing {needle!r}\n{combined}')


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-hosted-install-test-'))
    try:
        success_root = tmpdir / 'served-success'
        prepare_served_registry(success_root)
        with HostedRegistryServer(success_root) as server:
            repo = prepare_repo(tmpdir / 'success-case', server.base_url)
            assert_install_success(repo, tmpdir / 'installed-success', expected_integrity_state='unknown')

        backfilled_root = tmpdir / 'served-backfilled-success'
        prepare_served_registry(backfilled_root, backfill_manifest=True)
        with HostedRegistryServer(backfilled_root) as server:
            repo = prepare_repo(tmpdir / 'backfilled-success-case', server.base_url)
            assert_install_success(repo, tmpdir / 'installed-backfilled-success', expected_integrity_state='verified')

        bad_sha_root = tmpdir / 'served-bad-sha'
        prepare_served_registry(bad_sha_root, bundle_sha256='0' * 64)
        with HostedRegistryServer(bad_sha_root) as server:
            repo = prepare_repo(tmpdir / 'bad-sha-case', server.base_url)
            assert_install_failure(repo, tmpdir / 'installed-bad-sha', 'bundle digest')

        missing_provenance_root = tmpdir / 'served-missing-provenance'
        prepare_served_registry(missing_provenance_root, missing_provenance=True)
        with HostedRegistryServer(missing_provenance_root) as server:
            repo = prepare_repo(tmpdir / 'missing-provenance-case', server.base_url)
            assert_install_failure(repo, tmpdir / 'installed-missing-provenance', 'provenance')

        uninstalled_root = tmpdir / 'served-uninstallable'
        prepare_served_registry(uninstalled_root, installable=False)
        with HostedRegistryServer(uninstalled_root) as server:
            repo = prepare_repo(tmpdir / 'uninstallable-case', server.base_url)
            assert_install_failure(repo, tmpdir / 'installed-uninstallable', 'version-not-installable')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: hosted registry install checks passed')


if __name__ == '__main__':
    main()
