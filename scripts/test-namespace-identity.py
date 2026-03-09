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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-namespace-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Namespace Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'namespace@example.com'], cwd=repo)
    return tmpdir, repo


def scaffold_skill(repo: Path, stage: str, folder_name: str, *, name: str, version: str = '1.0.0', publisher=None, owners=None, author=None, depends_on=None, snapshot_of=None):
    skill_dir = repo / 'skills' / stage / folder_name
    shutil.copytree(repo / 'templates' / 'basic-skill', skill_dir)
    meta_path = skill_dir / '_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    owners = owners or [publisher or 'lvxiaoer']
    meta.update(
        {
            'name': name,
            'version': version,
            'status': stage,
            'summary': f'Fixture skill {name} for namespace identity tests',
            'owner': owners[0],
            'owners': owners,
            'author': author or owners[0],
            'maintainers': owners,
            'review_state': 'approved',
        }
    )
    if publisher:
        meta['publisher'] = publisher
        meta['qualified_name'] = f'{publisher}/{name}'
    else:
        meta.pop('publisher', None)
        meta.pop('qualified_name', None)
    if depends_on is not None:
        meta['depends_on'] = depends_on
    if snapshot_of is not None:
        meta['snapshot_of'] = snapshot_of
        meta['snapshot_created_at'] = '2026-03-09T00:00:00Z'
        meta['snapshot_label'] = 'namespace-transfer'
    write_json(meta_path, meta)
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {name}\n'
        f'description: Fixture skill {name}.\n'
        '---\n\n'
        f'# {name}\n',
        encoding='utf-8',
    )
    (skill_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {version} - 2026-03-09\n'
        '- Namespace identity fixture.\n',
        encoding='utf-8',
    )
    return skill_dir


def write_namespace_policy(repo: Path, *, publishers, transfers=None):
    base = json.loads((repo / 'policy' / 'namespace-policy.json').read_text(encoding='utf-8'))
    merged_publishers = dict(base.get('publishers') or {})
    merged_publishers.update(publishers)
    base['publishers'] = merged_publishers
    base['transfers'] = transfers or []
    write_json(repo / 'policy' / 'namespace-policy.json', base)


def scenario_check_skill_enforces_namespace_policy():
    tmpdir, repo = prepare_repo()
    try:
        skill_dir = scaffold_skill(
            repo,
            'active',
            'publisher-check',
            name='publisher-check',
            publisher='unauthorized',
            owners=['unauthorized'],
            author='unauthorized',
        )
        result = run([str(repo / 'scripts' / 'check-skill.sh'), str(skill_dir)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if "publisher 'unauthorized' is not declared" not in combined:
            fail(f'unexpected namespace-policy failure output:\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_qualified_dependency_ref_resolves():
    tmpdir, repo = prepare_repo()
    try:
        scaffold_skill(repo, 'active', 'helper', name='helper', publisher='lvxiaoer', owners=['lvxiaoer'], author='lvxiaoer')
        consumer_dir = scaffold_skill(
            repo,
            'active',
            'consumer',
            name='consumer',
            publisher='lvxiaoer',
            owners=['lvxiaoer'],
            author='lvxiaoer',
            depends_on=['lvxiaoer/helper@1.0.0'],
        )
        run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        plan = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'resolve-install-plan.py'),
                '--skill-dir',
                str(consumer_dir),
                '--json',
            ],
            cwd=repo,
        )
        payload = json.loads(plan.stdout)
        root = payload.get('root') or {}
        if root.get('qualified_name') != 'lvxiaoer/consumer':
            fail(f"unexpected root qualified_name {root.get('qualified_name')!r}")
        helper_steps = [step for step in payload.get('steps', []) if step.get('qualified_name') == 'lvxiaoer/helper']
        if len(helper_steps) != 1:
            fail(f'unexpected helper steps: {payload.get("steps")!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_transfer_requires_and_honors_policy():
    tmpdir, repo = prepare_repo()
    try:
        scaffold_skill(
            repo,
            'archived',
            'transfer-demo-1.0.0-20260309T000000Z',
            name='transfer-demo',
            version='1.0.0',
            publisher='oldpub',
            owners=['oldpub'],
            author='oldpub',
            snapshot_of='oldpub/transfer-demo@1.0.0',
        )
        scaffold_skill(
            repo,
            'active',
            'transfer-demo',
            name='transfer-demo',
            version='2.0.0',
            publisher='newpub',
            owners=['newpub'],
            author='newpub',
        )
        write_namespace_policy(
            repo,
            publishers={
                'oldpub': {'owners': ['oldpub'], 'maintainers': ['oldpub']},
                'newpub': {'owners': ['newpub'], 'maintainers': ['newpub']},
            },
            transfers=[],
        )
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'namespace transfer' not in combined:
            fail(f'expected unauthorized transfer failure, got:\n{combined}')

        write_namespace_policy(
            repo,
            publishers={
                'oldpub': {'owners': ['oldpub'], 'maintainers': ['oldpub']},
                'newpub': {'owners': ['newpub'], 'maintainers': ['newpub']},
            },
            transfers=[
                {
                    'name': 'transfer-demo',
                    'from': 'oldpub',
                    'to': 'newpub',
                    'approved_by': ['lvxiaoer'],
                    'note': 'Approved namespace migration',
                }
            ],
        )
        run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_check_skill_enforces_namespace_policy()
    scenario_qualified_dependency_ref_resolves()
    scenario_transfer_requires_and_honors_policy()
    print('OK: namespace identity checks passed')


if __name__ == '__main__':
    main()
