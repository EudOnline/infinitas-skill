#!/usr/bin/env python3
import json
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
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
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


def write_team_policy(repo: Path):
    write_json(
        repo / 'policy' / 'team-policy.json',
        {
            '$schema': '../schemas/team-policy.schema.json',
            'version': 1,
            'teams': {
                'maintainers-team': {
                    'members': ['alice', 'owner'],
                    'description': 'Primary maintainers for rotation tests.',
                },
                'security-team': {
                    'members': ['alice', 'bob', 'owner'],
                    'description': 'Security reviewers for rotation tests.',
                },
                'release-team': {
                    'members': ['owner'],
                    'description': 'Release reviewers currently unavailable because of owner conflict.',
                },
            },
        },
    )


def write_promotion_policy(repo: Path):
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
                'allow_owner_when_no_distinct_reviewer': False,
                'block_on_rejection': True,
                'groups': {
                    'maintainers': {
                        'teams': ['maintainers-team'],
                    },
                    'security': {
                        'teams': ['security-team'],
                    },
                    'release': {
                        'teams': ['release-team'],
                    },
                },
                'quorum': {
                    'defaults': {
                        'min_approvals': 1,
                        'required_groups': [],
                    },
                    'stage_overrides': {
                        'active': {
                            'min_approvals': 3,
                            'required_groups': ['maintainers', 'security', 'release'],
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
        'description: Fixture skill for reviewer rotation tests\n'
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
            'summary': 'Fixture skill for reviewer rotation checks.',
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
                    'note': 'Already counted maintainer approval',
                    'at': '2026-03-17T00:00:00Z',
                }
            ],
        },
    )
    return skill_dir


def scenario_reviewer_rotation_recommends_reviewers_and_escalations():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-reviewer-rotation-test-'))
    try:
        repo = copy_repo(tmpdir)
        write_team_policy(repo)
        write_promotion_policy(repo)
        write_skill(repo, 'rotation-fixture')

        suggested = run(
            [sys.executable, str(repo / 'scripts' / 'recommend-reviewers.py'), 'rotation-fixture', '--as-active', '--json'],
            cwd=repo,
        )
        payload = json.loads(suggested.stdout)
        groups = {item.get('group'): item for item in payload.get('group_recommendations') or []}
        security = groups.get('security') or {}
        release = groups.get('release') or {}
        eligible_security = [item.get('reviewer') for item in security.get('eligible_reviewers') or []]
        if 'bob' not in eligible_security:
            fail(f'expected bob to be recommended for security, got {payload!r}')
        excluded_security = security.get('excluded_reviewers') or []
        excluded_reasons = {item.get('reviewer'): item.get('reasons') or [] for item in excluded_security}
        if 'already-counted-reviewer' not in excluded_reasons.get('alice', []):
            fail(f'expected alice to be excluded as already-counted, got {payload!r}')
        if 'owner-conflict' not in excluded_reasons.get('owner', []):
            fail(f'expected owner to be excluded for owner conflict, got {payload!r}')
        if release.get('eligible_reviewers'):
            fail(f'expected release group to have no eligible reviewers, got {payload!r}')
        escalations = payload.get('escalations') or []
        release_escalation = next((item for item in escalations if item.get('group') == 'release'), None)
        if not release_escalation:
            fail(f'expected escalation guidance for release group, got {payload!r}')

        requested = run(
            [str(repo / 'scripts' / 'request-review.sh'), 'rotation-fixture', '--note', 'Need more reviewers', '--show-recommendations'],
            cwd=repo,
        )
        combined = requested.stdout + requested.stderr
        if 'bob' not in combined or 'release' not in combined.lower():
            fail(f'expected request-review output to surface reviewer guidance, got {combined!r}')

        status = run(
            [sys.executable, str(repo / 'scripts' / 'review-status.py'), 'rotation-fixture', '--as-active', '--json', '--show-recommendations'],
            cwd=repo,
        )
        status_payload = json.loads(status.stdout)
        status_recommendations = status_payload.get('recommendations') or {}
        status_escalations = status_recommendations.get('escalations') or []
        if not any(item.get('group') == 'release' for item in status_escalations):
            fail(f'expected review-status to surface escalation guidance, got {status_payload!r}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_reviewer_rotation_recommends_reviewers_and_escalations()
    print('OK: reviewer rotation checks passed')


if __name__ == '__main__':
    main()
