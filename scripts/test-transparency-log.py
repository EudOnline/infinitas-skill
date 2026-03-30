#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'

sys.path.insert(0, str(ROOT / 'scripts'))

from attestation_lib import AttestationError, publish_attestation_to_transparency_log  # noqa: E402


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_env(extra=None):
    env = os.environ.copy()
    env['INFINITAS_SKIP_RELEASE_TESTS'] = '1'
    env['INFINITAS_SKIP_ATTESTATION_TESTS'] = '1'
    env['INFINITAS_SKIP_DISTRIBUTION_TESTS'] = '1'
    env['INFINITAS_SKIP_BOOTSTRAP_TESTS'] = '1'
    env['INFINITAS_SKIP_AI_WRAPPER_TESTS'] = '1'
    env['INFINITAS_SKIP_COMPAT_PIPELINE_TESTS'] = '1'
    env['INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS'] = '1'
    if extra:
        env.update(extra)
    return env


def scaffold_fixture(repo: Path):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': FIXTURE_VERSION,
            'status': 'active',
            'summary': 'Fixture skill for transparency log tests',
            'owner': 'release-test',
            'owners': ['release-test'],
            'author': 'release-test',
            'review_state': 'approved',
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for transparency log tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated transparency log tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-17\n'
        '- Added transparency log test fixture.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-17T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for transparency log tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-17T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def seed_fresh_platform_evidence(repo: Path):
    fixtures = [
        ('codex', '2026-03-12T12:00:00Z'),
        ('claude', '2026-03-12T12:01:00Z'),
        ('openclaw', '2026-03-12T12:02:00Z'),
    ]
    for platform, checked_at in fixtures:
        path = repo / 'catalog' / 'compatibility-evidence' / platform / FIXTURE_NAME / f'{FIXTURE_VERSION}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                'platform': platform,
                'skill': FIXTURE_NAME,
                'version': FIXTURE_VERSION,
                'state': 'adapted',
                'checked_at': checked_at,
                'checker': f'check-{platform}-compat.py',
            },
        )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-transparency-log-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    (repo / 'config' / 'allowed_signers').write_text('', encoding='utf-8')
    scaffold_fixture(repo)
    seed_fresh_platform_evidence(repo)
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Release Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'release@example.com'], cwd=repo)
    run(['git', 'remote', 'add', 'origin', str(origin)], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    run(['git', 'push', '-u', 'origin', 'main'], cwd=repo)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', 'build fixture catalog'], cwd=repo)
    run(['git', 'push'], cwd=repo)

    key_path = tmpdir / 'release-test-key'
    identity = 'release-test'
    run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', identity, '-f', str(key_path)], cwd=repo)
    with (repo / 'config' / 'allowed_signers').open('a', encoding='utf-8') as handle:
        public_key = Path(str(key_path) + '.pub').read_text(encoding='utf-8').strip()
        handle.write(f'{identity} {public_key}\n')
    run(['git', 'config', 'gpg.format', 'ssh'], cwd=repo)
    run(['git', 'config', 'user.signingkey', str(key_path)], cwd=repo)
    run(['git', 'add', 'config/allowed_signers'], cwd=repo)
    run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo


def release_fixture(repo: Path):
    run(
        [
            str(repo / 'scripts' / 'release-skill.sh'),
            FIXTURE_NAME,
            '--push-tag',
            '--write-provenance',
        ],
        cwd=repo,
        env=make_env(),
    )
    return repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'


def set_transparency_config(repo: Path, mode: str, endpoint=None):
    signing_path = repo / 'config' / 'signing.json'
    signing = json.loads(signing_path.read_text(encoding='utf-8'))
    transparency = ((signing.get('attestation') or {}).get('transparency_log') or {})
    transparency['mode'] = mode
    transparency['endpoint'] = endpoint
    transparency['timeout_seconds'] = 5
    signing['attestation']['transparency_log'] = transparency
    write_json(signing_path, signing)


def commit_repo_change(repo: Path, message: str):
    run(['git', 'add', 'config/signing.json'], cwd=repo)
    run(['git', 'commit', '-m', message], cwd=repo)
    run(['git', 'push'], cwd=repo)


class TransparencyHandler(BaseHTTPRequestHandler):
    behavior = 'good'
    requests = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception:
            payload = None
        self.__class__.requests.append(
            {
                'path': self.path,
                'payload': payload,
            }
        )

        if self.__class__.behavior == 'malformed':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"entry_id":')
            return

        attestation_sha256 = None
        if isinstance(payload, dict):
            attestation_sha256 = payload.get('attestation_sha256')

        proof_sha256 = attestation_sha256
        echoed_sha256 = attestation_sha256
        if self.__class__.behavior == 'mismatch':
            proof_sha256 = '0' * 64
            echoed_sha256 = 'f' * 64

        response = {
            'entry_id': 'log-entry-1',
            'log_index': 7,
            'integrated_time': '2026-03-17T00:00:00Z',
            'attestation_sha256': echoed_sha256,
            'proof': {
                'hash_algorithm': 'sha256',
                'body_sha256': proof_sha256,
                'root_hash': 'a' * 64,
                'tree_size': 8,
                'inclusion_path': ['b' * 64, 'c' * 64],
            },
        }
        encoded = json.dumps(response, ensure_ascii=False).encode('utf-8')
        self.send_response(201)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class TransparencyServer:
    def __init__(self, behavior):
        TransparencyHandler.behavior = behavior
        TransparencyHandler.requests = []
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), TransparencyHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def endpoint(self):
        host, port = self.server.server_address
        return f'http://{host}:{port}/entries'

    @property
    def requests(self):
        return list(TransparencyHandler.requests)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def scenario_attestation_can_publish_to_transparency_log():
    tmpdir, repo = prepare_repo()
    try:
        provenance_path = release_fixture(repo)
        with TransparencyServer('good') as server:
            set_transparency_config(repo, 'advisory', server.endpoint)
            result = publish_attestation_to_transparency_log(provenance_path, root=repo)
            if result.get('mode') != 'advisory':
                fail(f"expected advisory transparency mode, got {result!r}")
            if result.get('published') is not True:
                fail(f'expected transparency publication success, got {result!r}')
            entry = result.get('entry') or {}
            if entry.get('entry_id') != 'log-entry-1':
                fail(f'expected normalized entry_id, got {entry!r}')
            if entry.get('log_index') != 7:
                fail(f'expected normalized log_index 7, got {entry!r}')
            if entry.get('attestation_sha256') != (server.requests[0].get('payload') or {}).get('attestation_sha256'):
                fail(f'expected logged digest to match request payload, got {entry!r} vs {server.requests!r}')
            request_payload = server.requests[0].get('payload') or {}
            if request_payload.get('skill', {}).get('name') != FIXTURE_NAME:
                fail(f'expected transparency payload to include skill metadata, got {request_payload!r}')
            if request_payload.get('source_snapshot', {}).get('tag') != f'skill/{FIXTURE_NAME}/v{FIXTURE_VERSION}':
                fail(f'expected transparency payload to include source snapshot tag, got {request_payload!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_advisory_mode_does_not_block_when_endpoint_is_missing():
    tmpdir, repo = prepare_repo()
    try:
        provenance_path = release_fixture(repo)
        set_transparency_config(repo, 'advisory', None)
        result = publish_attestation_to_transparency_log(provenance_path, root=repo)
        if result.get('published') is not False:
            fail(f'expected advisory mode to skip failed publication, got {result!r}')
        if 'endpoint' not in (result.get('error') or '').lower():
            fail(f'expected advisory failure to mention endpoint, got {result!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_required_mode_requires_endpoint():
    tmpdir, repo = prepare_repo()
    try:
        provenance_path = release_fixture(repo)
        set_transparency_config(repo, 'required', None)
        try:
            publish_attestation_to_transparency_log(provenance_path, root=repo)
        except AttestationError as exc:
            if 'endpoint' not in str(exc).lower():
                fail(f'expected missing-endpoint error, got {exc!r}')
        else:
            fail('expected required transparency mode to fail without an endpoint')
    finally:
        shutil.rmtree(tmpdir)


def scenario_malformed_transparency_response_fails_clearly():
    tmpdir, repo = prepare_repo()
    try:
        provenance_path = release_fixture(repo)
        with TransparencyServer('malformed') as server:
            set_transparency_config(repo, 'required', server.endpoint)
            try:
                publish_attestation_to_transparency_log(provenance_path, root=repo)
            except AttestationError as exc:
                message = str(exc).lower()
                if 'malformed' not in message and 'json' not in message:
                    fail(f'expected malformed-response error, got {exc!r}')
            else:
                fail('expected malformed transparency response to fail')
    finally:
        shutil.rmtree(tmpdir)


def scenario_proof_mismatch_fails_clearly():
    tmpdir, repo = prepare_repo()
    try:
        provenance_path = release_fixture(repo)
        with TransparencyServer('mismatch') as server:
            set_transparency_config(repo, 'required', server.endpoint)
            try:
                publish_attestation_to_transparency_log(provenance_path, root=repo)
            except AttestationError as exc:
                message = str(exc).lower()
                if 'proof' not in message and 'digest' not in message:
                    fail(f'expected proof-mismatch error, got {exc!r}')
            else:
                fail('expected proof mismatch to fail')
    finally:
        shutil.rmtree(tmpdir)


def scenario_release_flow_persists_transparency_proof_summary():
    tmpdir, repo = prepare_repo()
    try:
        with TransparencyServer('good') as server:
            set_transparency_config(repo, 'advisory', server.endpoint)
            commit_repo_change(repo, 'configure advisory transparency log')
            provenance_path = release_fixture(repo)

            provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
            transparency = provenance.get('transparency_log') or {}
            if transparency.get('mode') != 'advisory':
                fail(f'expected provenance transparency mode advisory, got {provenance!r}')
            entry_rel = transparency.get('entry_path')
            if not entry_rel:
                fail(f'expected provenance to record transparency entry path, got {provenance!r}')
            entry_path = repo / entry_rel
            if not entry_path.exists():
                fail(f'expected release flow to persist transparency entry {entry_path}')
            entry = json.loads(entry_path.read_text(encoding='utf-8'))
            if entry.get('entry_id') != 'log-entry-1':
                fail(f'expected persisted transparency entry_id, got {entry!r}')

            verified = run(
                [
                    sys.executable,
                    str(repo / 'scripts' / 'verify-attestation.py'),
                    str(provenance_path),
                    '--json',
                ],
                cwd=repo,
                env=make_env(),
            )
            verified_payload = json.loads(verified.stdout)
            transparency_summary = verified_payload.get('transparency_log') or {}
            if transparency_summary.get('verified') is not True:
                fail(f'expected verify-attestation to surface verified transparency summary, got {verified_payload!r}')
            if transparency_summary.get('entry_id') != 'log-entry-1':
                fail(f'expected verify-attestation entry_id, got {verified_payload!r}')

            release_state = run(
                [
                    sys.executable,
                    str(repo / 'scripts' / 'check-release-state.py'),
                    FIXTURE_NAME,
                    '--mode',
                    'local-tag',
                    '--json',
                ],
                cwd=repo,
                env=make_env(),
            )
            release_payload = json.loads(release_state.stdout)
            release_transparency = ((release_payload.get('release') or {}).get('transparency_log') or {})
            if release_transparency.get('verified') is not True:
                fail(f'expected check-release-state JSON to surface transparency summary, got {release_payload!r}')
            if release_transparency.get('entry_id') != 'log-entry-1':
                fail(f'expected check-release-state entry_id, got {release_payload!r}')

            run(['bash', str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo, env=make_env())
            catalog = json.loads((repo / 'catalog' / 'catalog.json').read_text(encoding='utf-8'))
            catalog_item = next((item for item in catalog.get('skills') or [] if item.get('name') == FIXTURE_NAME), None)
            if not catalog_item:
                fail(f'expected catalog entry for {FIXTURE_NAME}, got {catalog!r}')
            catalog_transparency = ((catalog_item.get('verified_distribution') or {}).get('transparency_log') or {})
            if catalog_transparency.get('verified') is not True:
                fail(f'expected catalog transparency summary, got {catalog_item!r}')
            if catalog_transparency.get('entry_id') != 'log-entry-1':
                fail(f'expected catalog transparency entry_id, got {catalog_item!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_verify_attestation_rejects_tampered_transparency_entry():
    tmpdir, repo = prepare_repo()
    try:
        with TransparencyServer('good') as server:
            set_transparency_config(repo, 'advisory', server.endpoint)
            commit_repo_change(repo, 'configure advisory transparency log')
            provenance_path = release_fixture(repo)
            provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
            entry_path = repo / ((provenance.get('transparency_log') or {}).get('entry_path') or '')
            if not entry_path.exists():
                fail(f'expected transparency entry before tamper check, got {provenance!r}')
            entry = json.loads(entry_path.read_text(encoding='utf-8'))
            entry['proof']['body_sha256'] = '0' * 64
            write_json(entry_path, entry)

            result = run(
                [
                    sys.executable,
                    str(repo / 'scripts' / 'verify-attestation.py'),
                    str(provenance_path),
                ],
                cwd=repo,
                env=make_env(),
                expect=1,
            )
            combined = result.stdout + result.stderr
            if 'transparency' not in combined.lower() and 'proof' not in combined.lower():
                fail(f'expected tampered transparency proof failure, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_required_transparency_mode_blocks_release_output():
    tmpdir, repo = prepare_repo()
    try:
        with TransparencyServer('mismatch') as server:
            set_transparency_config(repo, 'required', server.endpoint)
            commit_repo_change(repo, 'configure required transparency log')
            result = run(
                [
                    str(repo / 'scripts' / 'release-skill.sh'),
                    FIXTURE_NAME,
                    '--push-tag',
                    '--write-provenance',
                ],
                cwd=repo,
                env=make_env(),
                expect=1,
            )
            combined = result.stdout + result.stderr
            if 'transparency' not in combined.lower() and 'proof' not in combined.lower():
                fail(f'expected required transparency mode to fail clearly, got {combined!r}')

            provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
            if provenance_path.exists():
                fail(f'expected required transparency failure to block provenance output, found {provenance_path}')
            entry_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.transparency.json'
            if entry_path.exists():
                fail(f'expected no transparency entry on failed required release, found {entry_path}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_attestation_can_publish_to_transparency_log()
    scenario_advisory_mode_does_not_block_when_endpoint_is_missing()
    scenario_required_mode_requires_endpoint()
    scenario_malformed_transparency_response_fails_clearly()
    scenario_proof_mismatch_fails_clearly()
    scenario_release_flow_persists_transparency_proof_summary()
    scenario_verify_attestation_rejects_tampered_transparency_entry()
    scenario_required_transparency_mode_blocks_release_output()
    print('OK: transparency log checks passed')


if __name__ == '__main__':
    main()
