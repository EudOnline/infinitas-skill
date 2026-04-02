#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(cwd) / 'src')
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


def copy_repo(tmpdir: Path):
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '.worktrees', '.cache', '__pycache__', 'catalog'),
    )
    (repo / 'catalog').mkdir(exist_ok=True)
    return repo


def rewrite_policy(repo: Path):
    write_json(
        repo / 'policy' / 'promotion-policy.json',
        {
            '$schema': '../schemas/promotion-policy.schema.json',
            'version': 4,
            'active_requires': {
                'review_state': ['approved'],
                'require_changelog': True,
                'require_smoke_test': True,
                'require_owner': True,
            },
            'reviews': {
                'require_reviews_file': True,
                'reviewer_must_differ_from_owner': True,
                'block_on_rejection': True,
                'groups': {
                    'maintainers': {
                        'members': ['alice'],
                    },
                    'security': {
                        'members': ['bob'],
                    },
                },
                'quorum': {
                    'defaults': {
                        'min_approvals': 1,
                        'required_groups': [],
                    },
                    'stage_overrides': {
                        'active': {
                            'min_approvals': 2,
                            'required_groups': ['maintainers', 'security'],
                        },
                    },
                },
            },
            'high_risk_active_requires': {
                'min_maintainers': 1,
                'require_requires_block': True,
            },
            'dependency_rules': {
                'allow_name_only_refs': True,
                'allow_version_pins': True,
                'require_resolvable_refs_for_active': True,
                'auto_install_dependencies_default': True,
            },
        },
    )


def write_skill(repo: Path, name: str):
    skill_dir = repo / 'skills' / 'incubating' / name
    (skill_dir / 'tests').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {name}\n'
        'description: Fixture skill for platform review evidence tests\n'
        '---\n',
        encoding='utf-8',
    )
    write_json(
        skill_dir / '_meta.json',
        {
            'schema_version': 1,
            'name': name,
            'publisher': 'fixture',
            'qualified_name': f'fixture/{name}',
            'version': '0.1.0',
            'status': 'incubating',
            'summary': 'Fixture skill for imported review evidence checks.',
            'owner': 'owner',
            'maintainers': ['owner'],
            'review_state': 'draft',
            'risk_level': 'medium',
            'distribution': {
                'installable': True,
                'channel': 'git',
            },
            'tests': {
                'smoke': 'tests/smoke.md',
            },
        },
    )
    (skill_dir / 'CHANGELOG.md').write_text('# Changelog\n\n## 0.1.0 - 2026-03-17\n- Added fixture.\n', encoding='utf-8')
    (skill_dir / 'tests' / 'smoke.md').write_text('# Smoke\n\nFixture smoke test.\n', encoding='utf-8')
    write_json(
        skill_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [],
            'entries': [
                {
                    'reviewer': 'alice',
                    'decision': 'approved',
                    'note': 'Local repo approval',
                    'at': '2026-03-17T00:00:00Z',
                }
            ],
        },
    )
    return skill_dir


def write_review_evidence(skill_dir: Path, entries):
    write_json(
        skill_dir / 'review-evidence.json',
        {
            '$schema': '../schemas/review-evidence.schema.json',
            'version': 1,
            'entries': entries,
        },
    )


def init_git_repo(repo: Path):
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Fixture Maintainer'], cwd=repo)
    run(['git', 'config', 'user.email', 'fixture@example.com'], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture'], cwd=repo)


def scenario_imported_evidence_counts_toward_quorum_and_preserves_source():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-review-evidence-test-'))
    try:
        repo = copy_repo(tmpdir)
        rewrite_policy(repo)
        skill_dir = write_skill(repo, 'platform-review-fixture')
        write_review_evidence(
            skill_dir,
            [
                {
                    'source': 'github',
                    'source_kind': 'github-pull-review',
                    'source_ref': 'pr#42',
                    'reviewer': 'bob',
                    'decision': 'approved',
                    'at': '2026-03-17T01:00:00Z',
                    'url': 'https://example.test/pr/42#review-7',
                }
            ],
        )

        result = run(
            [sys.executable, str(repo / 'scripts' / 'review-status.py'), 'platform-review-fixture', '--as-active', '--json'],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('approval_count') != 2:
            fail(f"expected approval_count 2 with imported evidence, got {payload!r}")
        if payload.get('quorum_met') is not True:
            fail(f"expected quorum_met true with imported evidence, got {payload!r}")
        latest = payload.get('latest_decisions') or []
        alice = next((item for item in latest if item.get('reviewer') == 'alice'), None)
        bob = next((item for item in latest if item.get('reviewer') == 'bob'), None)
        if not alice or alice.get('source_kind') != 'repo-review':
            fail(f'expected local review decision provenance for alice, got {latest!r}')
        if not bob or bob.get('source_kind') != 'github-pull-review':
            fail(f'expected imported review decision provenance for bob, got {latest!r}')
        if bob.get('source_ref') != 'pr#42':
            fail(f"expected imported source_ref 'pr#42', got {bob!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_invalid_review_evidence_is_rejected():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-review-evidence-invalid-test-'))
    try:
        repo = copy_repo(tmpdir)
        rewrite_policy(repo)
        skill_dir = write_skill(repo, 'invalid-platform-review-fixture')
        write_review_evidence(
            skill_dir,
            [
                {
                    'source': 'github',
                    'source_kind': 'github-pull-review',
                    'reviewer': 'bob',
                    'decision': 'approved',
                    'at': '2026-03-17T01:00:00Z',
                }
            ],
        )

        result = run(
            [sys.executable, str(repo / 'scripts' / 'review-status.py'), 'invalid-platform-review-fixture', '--as-active', '--json'],
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'review evidence' not in combined.lower():
            fail(f'expected invalid review evidence failure, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_duplicate_imported_reviewers_are_rejected():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-review-evidence-duplicate-test-'))
    try:
        repo = copy_repo(tmpdir)
        rewrite_policy(repo)
        skill_dir = write_skill(repo, 'duplicate-platform-review-fixture')
        write_review_evidence(
            skill_dir,
            [
                {
                    'source': 'github',
                    'source_kind': 'github-pull-review',
                    'source_ref': 'pr#42',
                    'reviewer': 'bob',
                    'decision': 'approved',
                    'at': '2026-03-17T01:00:00Z',
                    'url': 'https://example.test/pr/42#review-7',
                },
                {
                    'source': 'github',
                    'source_kind': 'github-pull-review',
                    'source_ref': 'pr#42',
                    'reviewer': 'bob',
                    'decision': 'approved',
                    'at': '2026-03-17T01:05:00Z',
                    'url': 'https://example.test/pr/42#review-8',
                },
            ],
        )

        result = run(
            [sys.executable, str(repo / 'scripts' / 'review-status.py'), 'duplicate-platform-review-fixture', '--as-active', '--json'],
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'duplicate reviewer' not in combined.lower():
            fail(f'expected duplicate reviewer failure, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_import_cli_threads_platform_evidence_into_governance_surfaces():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-review-evidence-import-test-'))
    try:
        repo = copy_repo(tmpdir)
        rewrite_policy(repo)
        write_skill(repo, 'import-platform-review-fixture')
        init_git_repo(repo)
        input_path = repo / 'review-evidence-input.json'
        write_json(
            input_path,
            {
                '$schema': 'schemas/review-evidence.schema.json',
                'version': 1,
                'entries': [
                    {
                        'source': 'github',
                        'source_kind': 'github-pull-review',
                        'source_ref': 'pr#84',
                        'reviewer': 'bob',
                        'decision': 'approved',
                        'at': '2026-03-17T01:00:00Z',
                        'url': 'https://example.test/pr/84#review-3',
                    }
                ],
            },
        )

        imported = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'import-platform-review-evidence.py'),
                'import-platform-review-fixture',
                '--input',
                str(input_path),
                '--json',
            ],
            cwd=repo,
        )
        imported_payload = json.loads(imported.stdout)
        if imported_payload.get('imported_count') != 1:
            fail(f'expected imported_count 1, got {imported_payload!r}')

        promotion = run(
            [
                sys.executable,
                '-m',
                'infinitas_skill.cli.main',
                'policy',
                'check-promotion',
                str(repo / 'skills' / 'incubating' / 'import-platform-review-fixture'),
                '--as-active',
                '--json',
            ],
            cwd=repo,
        )
        promotion_payload = json.loads(promotion.stdout)
        evaluation = promotion_payload.get('evaluation') or {}
        if evaluation.get('approval_count') != 2:
            fail(f'expected promotion approval_count 2, got {promotion_payload!r}')
        imported_latest = next((item for item in evaluation.get('latest_decisions') or [] if item.get('reviewer') == 'bob'), None)
        if not imported_latest or imported_latest.get('source_kind') != 'github-pull-review':
            fail(f'expected imported latest decision in promotion output, got {promotion_payload!r}')

        release = run(
            [
                sys.executable,
                '-m',
                'infinitas_skill.cli.main',
                'release',
                'check-state',
                'import-platform-review-fixture',
                '--mode',
                'local-preflight',
                '--json',
            ],
            cwd=repo,
            expect=1,
        )
        release_payload = json.loads(release.stdout)
        release_latest = next((item for item in ((release_payload.get('review') or {}).get('latest_decisions') or []) if item.get('reviewer') == 'bob'), None)
        if not release_latest or release_latest.get('source_ref') != 'pr#84':
            fail(f'expected imported latest decision in release-state output, got {release_payload!r}')

        run(['bash', 'scripts/build-catalog.sh'], cwd=repo)
        catalog_payload = json.loads((repo / 'catalog' / 'catalog.json').read_text(encoding='utf-8'))
        catalog_item = next((item for item in catalog_payload.get('skills') or [] if item.get('name') == 'import-platform-review-fixture'), None)
        if not catalog_item:
            fail(f'expected catalog entry for import-platform-review-fixture, got {catalog_payload!r}')
        imported_reviewer = next((item for item in catalog_item.get('reviewers') or [] if item.get('reviewer') == 'bob'), None)
        if not imported_reviewer or imported_reviewer.get('source_kind') != 'github-pull-review':
            fail(f'expected imported reviewer provenance in catalog output, got {catalog_item!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_import_cli_rejects_missing_or_malformed_input():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-review-evidence-import-invalid-test-'))
    try:
        repo = copy_repo(tmpdir)
        rewrite_policy(repo)
        write_skill(repo, 'bad-import-platform-review-fixture')

        missing = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'import-platform-review-evidence.py'),
                'bad-import-platform-review-fixture',
                '--input',
                str(repo / 'missing-review-evidence.json'),
                '--json',
            ],
            cwd=repo,
            expect=1,
        )
        if 'missing input file' not in (missing.stdout + missing.stderr).lower():
            fail(f'expected missing input failure, got {(missing.stdout + missing.stderr)!r}')

        bad_input = repo / 'bad-review-evidence.json'
        bad_input.write_text('not-json\n', encoding='utf-8')
        malformed = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'import-platform-review-evidence.py'),
                'bad-import-platform-review-fixture',
                '--input',
                str(bad_input),
                '--json',
            ],
            cwd=repo,
            expect=1,
        )
        if 'invalid json' not in (malformed.stdout + malformed.stderr).lower():
            fail(f'expected malformed input failure, got {(malformed.stdout + malformed.stderr)!r}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_imported_evidence_counts_toward_quorum_and_preserves_source()
    scenario_invalid_review_evidence_is_rejected()
    scenario_duplicate_imported_reviewers_are_rejected()
    scenario_import_cli_threads_platform_evidence_into_governance_surfaces()
    scenario_import_cli_rejects_missing_or_malformed_input()
    print('OK: platform review evidence checks passed')


if __name__ == '__main__':
    main()
