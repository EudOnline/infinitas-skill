#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'
FIXTURE_TAG = f'skill/{FIXTURE_NAME}/v{FIXTURE_VERSION}'


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
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


def scaffold_fixture(repo: Path):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': FIXTURE_VERSION,
            'status': 'active',
            'summary': 'Fixture skill for stable attestation tests',
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
        'description: Fixture skill for release attestation tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated release attestation tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added stable attestation fixture.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-09T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for attestation tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-09T00:05:00Z',
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


def prepare_repo(include_signers=False):
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-attestation-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
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

    key_path = None
    identity = 'release-test'
    if include_signers:
        key_path = tmpdir / 'release-test-key'
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', identity, '-f', str(key_path)], cwd=repo)
        with (repo / 'config' / 'allowed_signers').open('a', encoding='utf-8') as handle:
            public_key = Path(str(key_path) + '.pub').read_text(encoding='utf-8').strip()
            handle.write(f'{identity} {public_key}\n')
        run(['git', 'config', 'gpg.format', 'ssh'], cwd=repo)
        run(['git', 'config', 'user.signingkey', str(key_path)], cwd=repo)
        run(['git', 'add', 'config/allowed_signers'], cwd=repo)
        run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
        run(['git', 'push'], cwd=repo)
    return tmpdir, repo, origin, key_path, identity


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def write_exception_policy(repo: Path, exceptions):
    path = repo / 'policy' / 'exception-policy.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    merged = list(payload.get('exceptions') or [])
    merged.extend(exceptions)
    payload['exceptions'] = merged
    write_json(path, payload)


def configure_delegated_audit_fixture(repo: Path):
    fixture_meta_path = repo / 'skills' / 'active' / FIXTURE_NAME / '_meta.json'
    meta = json.loads(fixture_meta_path.read_text(encoding='utf-8'))
    meta.update(
        {
            'publisher': 'fixture-labs',
            'owner': 'release-owner',
            'owners': ['release-owner'],
            'maintainers': ['release-maintainer'],
            'qualified_name': f'fixture-labs/{FIXTURE_NAME}',
        }
    )
    write_json(fixture_meta_path, meta)

    reviews_path = repo / 'skills' / 'active' / FIXTURE_NAME / 'reviews.json'
    reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
    reviews['entries'].append(
        {
            'reviewer': 'outsider',
            'decision': 'rejected',
            'at': '2026-03-09T00:06:00Z',
            'note': 'Unconfigured reviewer should be ignored',
        }
    )
    write_json(reviews_path, reviews)

    team_path = repo / 'policy' / 'team-policy.json'
    team_policy = json.loads(team_path.read_text(encoding='utf-8'))
    teams = team_policy.setdefault('teams', {})
    teams.update(
        {
            'release-owners': {
                'members': ['release-owner'],
            },
            'release-maintainers': {
                'members': ['release-maintainer'],
            },
            'release-signers': {
                'members': ['release-test'],
            },
            'release-captains': {
                'members': ['Release Fixture'],
            },
        }
    )
    write_json(team_path, team_policy)

    namespace_path = repo / 'policy' / 'namespace-policy.json'
    namespace_policy = json.loads(namespace_path.read_text(encoding='utf-8'))
    publishers = namespace_policy.setdefault('publishers', {})
    publishers['fixture-labs'] = {
        'owner_teams': ['release-owners'],
        'maintainer_teams': ['release-maintainers'],
        'authorized_signer_teams': ['release-signers'],
        'authorized_releaser_teams': ['release-captains'],
    }
    write_json(namespace_path, namespace_policy)


def write_ci_attestation(repo: Path):
    manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / FIXTURE_VERSION / 'manifest.json'
    bundle_path = manifest_path.parent / 'skill.tar.gz'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    bundle = manifest.get('bundle') or {}
    head_commit = run(['git', 'rev-parse', 'HEAD'], cwd=repo).stdout.strip()
    env = make_env(
        {
            'GITHUB_REPOSITORY': 'lvxiaoer/infinitas-skill',
            'GITHUB_WORKFLOW': 'release-attestation',
            'GITHUB_RUN_ID': '123456',
            'GITHUB_RUN_ATTEMPT': '1',
            'GITHUB_SHA': head_commit,
            'GITHUB_REF': f'refs/tags/{FIXTURE_TAG}',
            'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'GITHUB_SERVER_URL': 'https://github.com',
        }
    )
    result = run(
        [
            sys.executable,
            str(repo / 'scripts' / 'generate-ci-attestation.py'),
            FIXTURE_NAME,
            '--distribution-manifest-path',
            str(manifest_path.relative_to(repo)),
            '--distribution-bundle-path',
            str(bundle_path.relative_to(repo)),
            '--distribution-bundle-sha256',
            bundle.get('sha256') or '',
            '--distribution-bundle-size',
            str(bundle.get('size') or 0),
            '--distribution-bundle-root-dir',
            bundle.get('root_dir') or '',
            '--distribution-bundle-file-count',
            str(bundle.get('file_count') or 0),
        ],
        cwd=repo,
        env=env,
    )
    ci_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.ci.json'
    ci_path.write_text(result.stdout, encoding='utf-8')
    return ci_path, env


def scenario_release_notes_require_attestation():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        notes_path = tmpdir / 'release-notes.md'
        result = run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--notes-out', str(notes_path)],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'v9 attestation policy requires --write-provenance', 'notes attestation gate')
    finally:
        shutil.rmtree(tmpdir)


def scenario_verified_attestation_bundle_is_emitted():
    tmpdir, repo, _origin, _key_path, identity = prepare_repo(include_signers=True)
    try:
        result = run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'verified attestation:', 'verified attestation output')
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        signature_path = provenance_path.with_suffix(provenance_path.suffix + '.ssig')
        distribution_dir = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / FIXTURE_VERSION
        distribution_bundle = distribution_dir / 'skill.tar.gz'
        distribution_manifest = distribution_dir / 'manifest.json'
        distribution_index = repo / 'catalog' / 'distributions.json'
        if not signature_path.exists():
            fail(f'missing attestation signature {signature_path}')
        if not distribution_bundle.exists():
            fail(f'missing distribution bundle {distribution_bundle}')
        if not distribution_manifest.exists():
            fail(f'missing distribution manifest {distribution_manifest}')
        if not distribution_index.exists():
            fail(f'missing distribution index {distribution_index}')
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        if provenance.get('kind') != 'skill-release-attestation':
            fail(f"unexpected attestation kind {provenance.get('kind')!r}")
        if provenance.get('skill', {}).get('author') != identity:
            fail(f"expected skill.author {identity!r}, got {provenance.get('skill', {}).get('author')!r}")
        if provenance.get('attestation', {}).get('signer_identity') != identity:
            fail(
                f"expected signer_identity {identity!r}, got {provenance.get('attestation', {}).get('signer_identity')!r}"
            )
        reviewers = (provenance.get('review') or {}).get('reviewers') or []
        if len(reviewers) != 1 or reviewers[0].get('reviewer') != 'lvxiaoer':
            fail(f'unexpected reviewers payload {reviewers!r}')
        releaser = (provenance.get('release') or {}).get('releaser_identity')
        if releaser != 'Release Fixture':
            fail(f"expected releaser_identity 'Release Fixture', got {releaser!r}")
        if provenance.get('attestation', {}).get('signature_file') != signature_path.name:
            fail(
                f"expected signature_file {signature_path.name!r}, got {provenance.get('attestation', {}).get('signature_file')!r}"
            )
        if provenance.get('git', {}).get('expected_tag') != FIXTURE_TAG:
            fail(f"unexpected expected_tag {provenance.get('git', {}).get('expected_tag')!r}")
        if 'self' not in provenance.get('registry', {}).get('registries_consulted', []):
            fail(f"expected registry context to include self, got {provenance.get('registry', {}).get('registries_consulted')!r}")
        if not provenance.get('dependencies', {}).get('steps'):
            fail('expected dependency steps in attestation payload')
        root_steps = [step for step in provenance['dependencies']['steps'] if step.get('root')]
        if len(root_steps) != 1 or root_steps[0].get('name') != FIXTURE_NAME:
            fail(f"unexpected dependency root steps {root_steps!r}")
        distribution = provenance.get('distribution') or {}
        if (distribution.get('bundle') or {}).get('path') != str(distribution_bundle.relative_to(repo)):
            fail(f"unexpected bundle path {distribution.get('bundle')!r}")
        if distribution.get('manifest_path') != str(distribution_manifest.relative_to(repo)):
            fail(f"unexpected manifest path {distribution.get('manifest_path')!r}")
        run([sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)], cwd=repo, env=make_env())
        run([str(repo / 'scripts' / 'verify-provenance-ssh.sh'), str(provenance_path)], cwd=repo, env=make_env())
        run([sys.executable, str(repo / 'scripts' / 'verify-distribution-manifest.py'), str(distribution_manifest)], cwd=repo, env=make_env())
    finally:
        shutil.rmtree(tmpdir)


def scenario_provenance_persists_delegated_audit_details():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        configure_delegated_audit_fixture(repo)
        write_exception_policy(
            repo,
            [
                {
                    'id': 'dirty-worktree-waiver',
                    'scope': 'release',
                    'skills': [FIXTURE_NAME],
                    'rules': ['dirty-worktree'],
                    'approved_by': ['release-captain'],
                    'approved_at': '2026-03-15T00:10:00Z',
                    'justification': 'Emergency release preflight waiver',
                    'expires_at': '2099-01-01T00:00:00Z',
                }
            ],
        )
        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        run(
            [
                'git',
                'add',
                f'skills/active/{FIXTURE_NAME}/_meta.json',
                f'skills/active/{FIXTURE_NAME}/reviews.json',
                'policy/team-policy.json',
                'policy/namespace-policy.json',
                'policy/exception-policy.json',
                'catalog',
            ],
            cwd=repo,
        )
        run(['git', 'commit', '-m', 'configure delegated audit fixture'], cwd=repo)
        run(['git', 'push'], cwd=repo)
        dirty_marker = repo / '.planning' / 'dirty-worktree.txt'
        dirty_marker.parent.mkdir(parents=True, exist_ok=True)
        dirty_marker.write_text('dirty\n', encoding='utf-8')
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        review = provenance.get('review') or {}
        latest_decisions = review.get('latest_decisions') or []
        if len(latest_decisions) != 2:
            fail(f'expected provenance review.latest_decisions, got {review!r}')
        groups = review.get('configured_groups') or {}
        security = groups.get('security') or {}
        if 'lvxiaoer' not in (security.get('resolved_members') or []):
            fail(f'unexpected provenance review.configured_groups.security {security!r}')
        ignored_decisions = review.get('ignored_decisions') or []
        if len(ignored_decisions) != 1 or ignored_decisions[0].get('reviewer') != 'outsider':
            fail(f'unexpected provenance review.ignored_decisions {ignored_decisions!r}')

        release = provenance.get('release') or {}
        delegated_teams = release.get('delegated_teams') or {}
        if delegated_teams.get('owner_teams') != ['release-owners']:
            fail(f'unexpected provenance release.delegated_teams {delegated_teams!r}')
        exception_usage = release.get('exception_usage') or []
        exception = next((item for item in exception_usage if item.get('id') == 'dirty-worktree-waiver'), None)
        if not exception:
            fail(f'unexpected provenance release.exception_usage {exception_usage!r}')
        if exception.get('justification') != 'Emergency release preflight waiver':
            fail(f'unexpected provenance exception justification {exception!r}')
        if exception.get('approved_by') != ['release-captain']:
            fail(f'unexpected provenance exception approved_by {exception!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_tamper_breaks_attestation():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        provenance['skill']['summary'] = 'tampered'
        provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'FAIL:', 'tampered attestation failure')
    finally:
        shutil.rmtree(tmpdir)


def scenario_both_mode_requires_ssh_and_ci():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        ci_path, env = write_ci_attestation(repo)
        signing_config_path = repo / 'config' / 'signing.json'
        signing_config = json.loads(signing_config_path.read_text(encoding='utf-8'))
        signing_config['attestation']['policy']['release_trust_mode'] = 'both'
        signing_config_path.write_text(json.dumps(signing_config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path), '--json'],
            cwd=repo,
            env=env,
        )
        payload = json.loads(result.stdout)
        if payload.get('policy_mode') != 'both':
            fail(f"expected policy_mode 'both', got {payload.get('policy_mode')!r}")
        if payload.get('formats_verified') != ['ssh', 'ci']:
            fail(f"expected formats_verified ['ssh', 'ci'], got {payload.get('formats_verified')!r}")

        ci_payload = json.loads(ci_path.read_text(encoding='utf-8'))
        ci_payload['ci']['workflow'] = 'unexpected-workflow'
        ci_path.write_text(json.dumps(ci_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)],
            cwd=repo,
            expect=1,
            env=env,
        )
        assert_contains(result.stdout + result.stderr, 'FAIL:', 'mixed-mode verifier failure')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_release_notes_require_attestation()
    scenario_verified_attestation_bundle_is_emitted()
    scenario_provenance_persists_delegated_audit_details()
    scenario_tamper_breaks_attestation()
    scenario_both_mode_requires_ssh_and_ci()
    print('OK: attestation verification checks passed')


if __name__ == '__main__':
    main()
