#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    env = os.environ.copy()
    env['INFINITAS_SKIP_RELEASE_TESTS'] = '1'
    env['INFINITAS_SKIP_ATTESTATION_TESTS'] = '1'
    env['INFINITAS_SKIP_DISTRIBUTION_TESTS'] = '1'
    env['INFINITAS_SKIP_BOOTSTRAP_TESTS'] = '1'
    env['INFINITAS_SKIP_AI_WRAPPER_TESTS'] = '1'
    env['INFINITAS_SKIP_COMPAT_PIPELINE_TESTS'] = '1'
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
            'summary': 'Fixture skill for stable release invariant tests',
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
        'description: Fixture skill for release invariant tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated release invariant tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added stable release invariant fixture.\n',
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
                    'note': 'Fixture approval for stable release tests',
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


def prepare_repo(include_signers=False):
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-release-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    (repo / 'config' / 'allowed_signers').write_text('', encoding='utf-8')
    scaffold_fixture(repo)
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
    write_json(
        repo / 'policy' / 'exception-policy.json',
        {
            '$schema': '../schemas/exception-policy.schema.json',
            'version': 1,
            'exceptions': exceptions,
        },
    )


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

    write_json(
        repo / 'policy' / 'team-policy.json',
        {
            '$schema': '../schemas/team-policy.schema.json',
            'version': 1,
            'teams': {
                'release-owners': {
                    'members': ['release-owner'],
                },
                'release-maintainers': {
                    'members': ['release-maintainer'],
                },
                'security-review': {
                    'members': ['lvxiaoer'],
                },
                'release-signers': {
                    'members': ['release-test'],
                },
                'release-captains': {
                    'members': ['Release Fixture'],
                },
            },
        },
    )
    write_json(
        repo / 'policy' / 'namespace-policy.json',
        {
            '$schema': '../schemas/namespace-policy.schema.json',
            'version': 1,
            'publishers': {
                'fixture-labs': {
                    'owner_teams': ['release-owners'],
                    'maintainer_teams': ['release-maintainers'],
                    'authorized_signer_teams': ['release-signers'],
                    'authorized_releaser_teams': ['release-captains'],
                }
            },
        },
    )
    write_json(
        repo / 'policy' / 'promotion-policy.json',
        {
            '$schema': '../schemas/promotion-policy.schema.json',
            'version': 4,
            'active_requires': {
                'review_state': ['approved'],
                'require_changelog': True,
                'require_owner': True,
            },
            'reviews': {
                'require_reviews_file': True,
                'reviewer_must_differ_from_owner': True,
                'allow_owner_when_no_distinct_reviewer': False,
                'block_on_rejection': True,
                'groups': {
                    'security': {
                        'teams': ['security-review'],
                    }
                },
                'quorum': {
                    'stage_overrides': {
                        'active': {
                            'min_approvals': 1,
                            'required_groups': ['security'],
                        }
                    }
                },
            },
        },
    )


def scenario_missing_signers_blocks_tag_creation():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=False)
    try:
        result = run([str(repo / 'scripts' / 'release-skill-tag.sh'), FIXTURE_NAME, '--create'], cwd=repo, expect=1, env=make_env())
        assert_contains(result.stderr, 'config/allowed_signers has no signer entries', 'missing signers error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_missing_tag_blocks_release():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        result = run([str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME], cwd=repo, expect=1, env=make_env())
        combined = result.stdout + result.stderr
        assert_contains(combined, 'expected release tag is missing', 'missing tag error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_dirty_worktree_is_rejected():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-release-state.py'), FIXTURE_NAME, '--mode', 'preflight'],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        assert_contains(result.stdout, 'worktree is dirty', 'dirty worktree error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_dirty_worktree_exception_can_pass_preflight():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
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
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-release-state.py'), FIXTURE_NAME, '--mode', 'preflight', '--json'],
            cwd=repo,
            env=make_env(),
        )
        payload = json.loads(result.stdout)
        if payload.get('release_ready') is not True:
            fail(f'expected dirty-worktree exception to allow preflight release, got {payload!r}')
        usage = payload.get('exception_usage') or []
        if not any(item.get('id') == 'dirty-worktree-waiver' for item in usage):
            fail(f'expected exception_usage to mention dirty-worktree-waiver, got {usage!r}')
        trace = payload.get('policy_trace') or {}
        exceptions = trace.get('exceptions') or []
        record = next((item for item in exceptions if item.get('id') == 'dirty-worktree-waiver'), None)
        if not record:
            fail(f'expected policy_trace.exceptions to mention dirty-worktree-waiver, got {exceptions!r}')
        if record.get('justification') != 'Emergency release preflight waiver':
            fail(f'expected trace justification to survive, got {record!r}')
        if record.get('expires_at') != '2099-01-01T00:00:00Z':
            fail(f'expected trace expires_at to survive, got {record!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_release_state_exports_delegated_audit_details():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        configure_delegated_audit_fixture(repo)
        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
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
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-release-state.py'), FIXTURE_NAME, '--mode', 'preflight', '--json'],
            cwd=repo,
            env=make_env(),
        )
        payload = json.loads(result.stdout)
        if payload.get('release_ready') is not True:
            fail(f'expected delegated audit fixture to pass preflight, got {payload!r}')

        review = payload.get('review') or {}
        if review.get('effective_review_state') != 'approved':
            fail(f"expected effective_review_state 'approved', got {review!r}")
        if review.get('required_groups') != ['security']:
            fail(f"expected required_groups ['security'], got {review.get('required_groups')!r}")
        if review.get('approval_count') != 1:
            fail(f"expected approval_count 1, got {review.get('approval_count')!r}")
        if review.get('blocking_rejection_count') != 0:
            fail(f"expected blocking_rejection_count 0, got {review.get('blocking_rejection_count')!r}")
        if review.get('quorum_met') is not True:
            fail(f'expected quorum_met true, got {review.get("quorum_met")!r}')
        if review.get('review_gate_pass') is not True:
            fail(f'expected review_gate_pass true, got {review.get("review_gate_pass")!r}')
        covered_groups = review.get('covered_groups') or []
        if 'security' not in covered_groups:
            fail(f'expected covered_groups to include security, got {covered_groups!r}')
        if review.get('missing_groups') != []:
            fail(f"expected no missing_groups, got {review.get('missing_groups')!r}")
        latest_decisions = review.get('latest_decisions') or []
        if len(latest_decisions) != 2:
            fail(f'expected two latest_decisions entries, got {latest_decisions!r}')
        counted_approval = next((item for item in latest_decisions if item.get('reviewer') == 'lvxiaoer'), None)
        if not counted_approval or 'security' not in (counted_approval.get('groups') or []):
            fail(f'expected lvxiaoer latest_decisions entry to cover security, got {latest_decisions!r}')
        ignored_decisions = review.get('ignored_decisions') or []
        if len(ignored_decisions) != 1 or ignored_decisions[0].get('reviewer') != 'outsider':
            fail(f'expected outsider ignored_decisions entry, got {ignored_decisions!r}')
        groups = review.get('configured_groups') or {}
        security = groups.get('security') or {}
        if security.get('teams') != ['security-review']:
            fail(f'unexpected configured_groups.security.teams {security!r}')

        release = payload.get('release') or {}
        delegated_teams = release.get('delegated_teams') or {}
        if delegated_teams.get('owner_teams') != ['release-owners']:
            fail(f'unexpected delegated owner_teams {delegated_teams!r}')
        if delegated_teams.get('authorized_releaser_teams') != ['release-captains']:
            fail(f'unexpected delegated authorized_releaser_teams {delegated_teams!r}')
        release_exception_usage = release.get('exception_usage') or []
        if not any(item.get('id') == 'dirty-worktree-waiver' for item in release_exception_usage):
            fail(f'expected release.exception_usage to mention dirty-worktree-waiver, got {release_exception_usage!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_expired_dirty_worktree_exception_is_ignored():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
        write_exception_policy(
            repo,
            [
                {
                    'id': 'dirty-worktree-waiver-expired',
                    'scope': 'release',
                    'skills': [FIXTURE_NAME],
                    'rules': ['dirty-worktree'],
                    'approved_by': ['release-captain'],
                    'approved_at': '2024-01-01T00:10:00Z',
                    'justification': 'Expired dirty-worktree waiver',
                    'expires_at': '2024-01-02T00:00:00Z',
                }
            ],
        )
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-release-state.py'), FIXTURE_NAME, '--mode', 'preflight', '--json'],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        payload = json.loads(result.stdout)
        errors = '\n'.join(payload.get('errors') or [])
        if 'worktree is dirty' not in errors:
            fail(f'expected expired exception to be ignored, got {payload!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_ahead_of_upstream_is_rejected():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        (repo / 'AHEAD.txt').write_text('ahead\n', encoding='utf-8')
        run(['git', 'add', 'AHEAD.txt'], cwd=repo)
        run(['git', 'commit', '-m', 'ahead change'], cwd=repo)
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-release-state.py'), FIXTURE_NAME, '--mode', 'preflight'],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        assert_contains(result.stdout, 'ahead of origin/main by 1 commit', 'ahead-of-upstream error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_unsigned_tag_is_rejected():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        run([str(repo / 'scripts' / 'release-skill-tag.sh'), FIXTURE_NAME, '--create', '--unsigned'], cwd=repo, env=make_env())
        run(['git', 'push', 'origin', f'refs/tags/{FIXTURE_TAG}'], cwd=repo)
        result = run([str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME], cwd=repo, expect=1, env=make_env())
        combined = result.stdout + result.stderr
        assert_contains(combined, 'stable releases require a signed annotated tag', 'unsigned tag error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_signed_tag_must_be_pushed():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        run([str(repo / 'scripts' / 'release-skill-tag.sh'), FIXTURE_NAME, '--create'], cwd=repo, env=make_env())
        result = run([str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME], cwd=repo, expect=1, env=make_env())
        combined = result.stdout + result.stderr
        assert_contains(combined, 'is not pushed to origin', 'unpushed tag error')
    finally:
        shutil.rmtree(tmpdir)


def scenario_signed_pushed_release_succeeds():
    tmpdir, repo, _origin, _key_path, identity = prepare_repo(include_signers=True)
    try:
        notes_path = tmpdir / 'release-notes.md'
        result = run(
            [
                str(repo / 'scripts' / 'release-skill.sh'),
                FIXTURE_NAME,
                '--push-tag',
                '--notes-out',
                str(notes_path),
                '--write-provenance',
            ],
            cwd=repo,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'release_ref: refs/tags/' + FIXTURE_TAG, 'stable release summary')
        notes = notes_path.read_text(encoding='utf-8')
        assert_contains(notes, '## Source Snapshot', 'release notes snapshot block')
        assert_contains(notes, FIXTURE_TAG, 'release notes tag reference')
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        signature_path = provenance_path.with_suffix(provenance_path.suffix + '.ssig')
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        if provenance['source_snapshot']['immutable'] is not True:
            fail(f"expected immutable source snapshot, got {provenance['source_snapshot']['immutable']!r}")
        if provenance['source_snapshot']['pushed'] is not True:
            fail(f"expected pushed source snapshot, got {provenance['source_snapshot']['pushed']!r}")
        if provenance['git']['release_ref'] != f'refs/tags/{FIXTURE_TAG}':
            fail(f"unexpected release_ref {provenance['git']['release_ref']!r}")
        head = run(['git', 'rev-parse', 'HEAD'], cwd=repo).stdout.strip()
        if provenance['git']['commit'] != head:
            fail(f"expected provenance commit {head}, got {provenance['git']['commit']!r}")
        remote_tag = run(['git', 'ls-remote', '--tags', 'origin', f'refs/tags/{FIXTURE_TAG}^{{}}'], cwd=repo).stdout.strip().split('\t', 1)[0]
        if provenance['git']['remote_tag_commit'] != remote_tag:
            fail(f"expected remote_tag_commit {remote_tag}, got {provenance['git']['remote_tag_commit']!r}")
        if provenance.get('kind') != 'skill-release-attestation':
            fail(f"unexpected provenance kind {provenance.get('kind')!r}")
        if provenance.get('attestation', {}).get('signer_identity') != identity:
            fail(
                f"expected attestation signer_identity {identity!r}, got {provenance.get('attestation', {}).get('signer_identity')!r}"
            )
        if not provenance.get('registry', {}).get('resolved'):
            fail('expected resolved registry context in release attestation')
        if not provenance.get('dependencies', {}).get('steps'):
            fail('expected dependency steps in release attestation')
        if not signature_path.exists():
            fail(f'missing SSH attestation signature {signature_path}')
        run([sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)], cwd=repo, env=make_env())
    finally:
        shutil.rmtree(tmpdir)


def scenario_existing_signed_tag_can_resume_release():
    tmpdir, repo, _origin, _key_path, identity = prepare_repo(include_signers=True)
    try:
        run([str(repo / 'scripts' / 'release-skill-tag.sh'), FIXTURE_NAME, '--create', '--push'], cwd=repo, env=make_env())
        result = run(
            [
                str(repo / 'scripts' / 'release-skill.sh'),
                FIXTURE_NAME,
                '--push-tag',
                '--write-provenance',
                '--releaser',
                identity,
            ],
            cwd=repo,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'verified attestation:', 'resume release attestation summary')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_missing_signers_blocks_tag_creation()
    scenario_missing_tag_blocks_release()
    scenario_dirty_worktree_is_rejected()
    scenario_dirty_worktree_exception_can_pass_preflight()
    scenario_release_state_exports_delegated_audit_details()
    scenario_expired_dirty_worktree_exception_is_ignored()
    scenario_ahead_of_upstream_is_rejected()
    scenario_unsigned_tag_is_rejected()
    scenario_signed_tag_must_be_pushed()
    scenario_signed_pushed_release_succeeds()
    scenario_existing_signed_tag_can_resume_release()
    print('OK: release invariant checks passed')


if __name__ == '__main__':
    main()
