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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_skill(repo: Path, name: str):
    skill_dir = repo / 'skills' / 'incubating' / name
    (skill_dir / 'tests').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {name}\n'
        'description: Fixture skill for review governance checks\n'
        '---\n',
        encoding='utf-8',
    )
    write_json(
        skill_dir / '_meta.json',
        {
            'name': name,
            'version': '0.1.0',
            'status': 'incubating',
            'summary': 'Fixture skill for review governance checks.',
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
    (skill_dir / 'CHANGELOG.md').write_text('# Changelog\n\n## 0.1.0 - 2026-03-09\n- Added fixture.\n', encoding='utf-8')
    (skill_dir / 'tests' / 'smoke.md').write_text('# Smoke\n\nFixture smoke test.\n', encoding='utf-8')
    write_json(skill_dir / 'reviews.json', {'version': 1, 'requests': [], 'entries': []})
    return skill_dir


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


def main():
    with tempfile.TemporaryDirectory(prefix='infinitas-review-test-') as tmpdir:
        repo = Path(tmpdir) / 'repo'
        shutil.copytree(
            ROOT,
            repo,
            ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'catalog'),
        )
        (repo / 'catalog').mkdir(exist_ok=True)
        rewrite_policy(repo)
        write_skill(repo, 'quorum-fixture')

        run([str(repo / 'scripts' / 'request-review.sh'), 'quorum-fixture', '--note', 'Ready for active'], cwd=repo)
        meta = json.loads((repo / 'skills' / 'incubating' / 'quorum-fixture' / '_meta.json').read_text(encoding='utf-8'))
        if meta.get('review_state') != 'under-review':
            fail(f"expected request-review to sync review_state to under-review, got {meta.get('review_state')!r}")

        run([str(repo / 'scripts' / 'approve-skill.sh'), 'quorum-fixture', '--reviewer', 'mallory'], cwd=repo, expect=1)
        run([str(repo / 'scripts' / 'approve-skill.sh'), 'quorum-fixture', '--reviewer', 'alice', '--decision', 'approved'], cwd=repo)

        status = run([sys.executable, str(repo / 'scripts' / 'review-status.py'), 'quorum-fixture', '--as-active'], cwd=repo)
        if 'missing_groups: security' not in status.stdout:
            fail(f'missing_groups output did not mention security\n{status.stdout}')
        run([sys.executable, str(repo / 'scripts' / 'review-status.py'), 'quorum-fixture', '--as-active', '--require-pass'], cwd=repo, expect=1)
        run([str(repo / 'scripts' / 'promote-skill.sh'), 'quorum-fixture'], cwd=repo, expect=1)

        run([str(repo / 'scripts' / 'approve-skill.sh'), 'quorum-fixture', '--reviewer', 'bob', '--decision', 'rejected'], cwd=repo)
        status = run([sys.executable, str(repo / 'scripts' / 'review-status.py'), 'quorum-fixture', '--as-active'], cwd=repo)
        if 'effective_review_state: rejected' not in status.stdout:
            fail(f'rejected status missing from output\n{status.stdout}')
        if 'blocking_rejections: 1' not in status.stdout:
            fail(f'blocking rejection count missing from output\n{status.stdout}')

        run([str(repo / 'scripts' / 'approve-skill.sh'), 'quorum-fixture', '--reviewer', 'bob', '--decision', 'approved'], cwd=repo)
        status = run([sys.executable, str(repo / 'scripts' / 'review-status.py'), 'quorum-fixture', '--as-active', '--require-pass'], cwd=repo)
        if 'effective_review_state: approved' not in status.stdout:
            fail(f'approved status missing from output\n{status.stdout}')

        run([str(repo / 'scripts' / 'promote-skill.sh'), 'quorum-fixture'], cwd=repo)
        active_skill = repo / 'skills' / 'active' / 'quorum-fixture'
        if not active_skill.is_dir():
            fail('promote-skill.sh did not move the fixture skill to skills/active')
        active_meta = json.loads((active_skill / '_meta.json').read_text(encoding='utf-8'))
        if active_meta.get('status') != 'active':
            fail(f"expected promoted skill status to be active, got {active_meta.get('status')!r}")
        if active_meta.get('review_state') != 'approved':
            fail(f"expected promoted skill review_state to be approved, got {active_meta.get('review_state')!r}")

        active_catalog = json.loads((repo / 'catalog' / 'active.json').read_text(encoding='utf-8'))
        matching = [item for item in active_catalog.get('skills', []) if item.get('name') == 'quorum-fixture']
        if len(matching) != 1:
            fail(f'expected one catalog entry for quorum-fixture, got {len(matching)}')
        item = matching[0]
        if item.get('review_state') != 'approved':
            fail(f"expected catalog review_state=approved, got {item.get('review_state')!r}")
        if item.get('declared_review_state') != 'approved':
            fail(f"expected catalog declared_review_state=approved, got {item.get('declared_review_state')!r}")
        if item.get('required_reviewer_groups') != ['maintainers', 'security']:
            fail(f"unexpected required_reviewer_groups {item.get('required_reviewer_groups')!r}")
        if item.get('missing_reviewer_groups') != []:
            fail(f"expected no missing reviewer groups, got {item.get('missing_reviewer_groups')!r}")
        if item.get('quorum_met') is not True:
            fail(f"expected quorum_met true, got {item.get('quorum_met')!r}")
        if item.get('review_gate_pass') is not True:
            fail(f"expected review_gate_pass true, got {item.get('review_gate_pass')!r}")

    print('OK: review governance checks passed')


if __name__ == '__main__':
    main()
