#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
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


def iso_at(day: date, hour: int, minute: int = 0) -> str:
    return f'{day.isoformat()}T{hour:02d}:{minute:02d}:00Z'


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-compat-evidence-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def scaffold_skill(repo: Path):
    skill_dir = repo / 'skills' / 'active' / 'triple-demo'
    skill_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        skill_dir / '_meta.json',
        {
            'name': 'triple-demo',
            'version': '1.2.3',
            'status': 'active',
            'summary': 'Triple platform compatibility demo',
            'owner': 'compat-team',
            'publisher': 'openai',
            'review_state': 'approved',
            'risk_level': 'low',
            'maintainers': ['compat-team'],
            'tags': ['compatibility'],
            'agent_compatible': ['claude', 'codex', 'openclaw'],
            'requires': {
                'tools': ['python3'],
                'env': [],
            },
            'entrypoints': {
                'skill_md': 'SKILL.md',
            },
            'tests': {
                'smoke': 'tests/smoke.md',
            },
            'distribution': {
                'installable': True,
                'channel': 'stable',
            },
        },
    )
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: triple-demo\ndescription: Triple platform demo\n---\n\n# Triple Demo\n',
        encoding='utf-8',
    )
    (skill_dir / 'tests').mkdir(exist_ok=True)
    (skill_dir / 'tests' / 'smoke.md').write_text('# smoke\n', encoding='utf-8')
    (skill_dir / 'REVIEWS.json').write_text('{"entries": []}\n', encoding='utf-8')
    return skill_dir


def write_evidence(repo: Path, *, codex_checked_day: date, openclaw_checked_day: date):
    write_json(
        repo / 'catalog' / 'compatibility-evidence' / 'codex' / 'triple-demo' / '1.2.3.json',
        {
            'platform': 'codex',
            'skill': 'triple-demo',
            'version': '1.2.3',
            'state': 'adapted',
            'checked_at': iso_at(codex_checked_day, 12),
            'checker': 'check-codex-compat.py',
        },
    )
    write_json(
        repo / 'catalog' / 'compatibility-evidence' / 'openclaw' / 'triple-demo' / '1.2.3.json',
        {
            'platform': 'openclaw',
            'skill': 'triple-demo',
            'version': '1.2.3',
            'state': 'adapted',
            'checked_at': iso_at(openclaw_checked_day, 12, 5),
            'checker': 'check-openclaw-compat.py',
        },
    )


def write_platform_last_verified(repo: Path, platform: str, value: str):
    path = repo / 'profiles' / f'{platform}.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    contract = payload.get('contract') if isinstance(payload.get('contract'), dict) else {}
    contract['last_verified'] = value
    payload['contract'] = contract
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    tmpdir, repo = prepare_repo()
    try:
        today = date.today()
        codex_checked_day = today - timedelta(days=3)
        openclaw_checked_day = today - timedelta(days=3)
        codex_contract_day = today - timedelta(days=2)
        openclaw_contract_day = today - timedelta(days=3)
        claude_contract_day = today - timedelta(days=4)
        scaffold_skill(repo)
        write_evidence(
            repo,
            codex_checked_day=codex_checked_day,
            openclaw_checked_day=openclaw_checked_day,
        )
        write_platform_last_verified(repo, 'codex', codex_contract_day.isoformat())
        write_platform_last_verified(repo, 'openclaw', openclaw_contract_day.isoformat())
        write_platform_last_verified(repo, 'claude', claude_contract_day.isoformat())
        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)

        catalog = json.loads((repo / 'catalog' / 'compatibility.json').read_text(encoding='utf-8'))
        skills = catalog.get('skills')
        if not isinstance(skills, list) or not skills:
            fail(f'expected compatibility catalog to include skills entries, got {catalog!r}')

        entry = next((item for item in skills if item.get('name') == 'triple-demo'), None)
        if entry is None:
            fail(f'expected triple-demo entry in compatibility catalog, got {skills!r}')

        if entry.get('declared_support') != ['claude', 'codex', 'openclaw']:
            fail(f"unexpected declared support: {entry.get('declared_support')!r}")

        verified = entry.get('verified_support') or {}
        if verified.get('codex', {}).get('state') != 'adapted':
            fail(f"expected codex verified_support adapted, got {verified.get('codex')!r}")
        if verified.get('codex', {}).get('freshness_state') != 'stale':
            fail(f"expected codex freshness_state stale, got {verified.get('codex')!r}")
        if verified.get('codex', {}).get('freshness_reason') != 'contract-newer-than-evidence':
            fail(f"expected codex freshness_reason contract-newer-than-evidence, got {verified.get('codex')!r}")
        if verified.get('codex', {}).get('contract_last_verified') != codex_contract_day.isoformat():
            fail(f"expected codex contract_last_verified 2026-03-13, got {verified.get('codex')!r}")
        if verified.get('openclaw', {}).get('state') != 'adapted':
            fail(f"expected openclaw verified_support adapted, got {verified.get('openclaw')!r}")
        if verified.get('openclaw', {}).get('freshness_state') != 'fresh':
            fail(f"expected openclaw freshness_state fresh, got {verified.get('openclaw')!r}")
        if verified.get('openclaw', {}).get('freshness_reason') != 'not-applicable':
            fail(f"expected openclaw freshness_reason not-applicable, got {verified.get('openclaw')!r}")
        if verified.get('openclaw', {}).get('contract_last_verified') != openclaw_contract_day.isoformat():
            fail(f"expected openclaw contract_last_verified 2026-03-12, got {verified.get('openclaw')!r}")
        expected_openclaw_fresh_until = iso_at(openclaw_checked_day + timedelta(days=30), 12, 5)
        if verified.get('openclaw', {}).get('fresh_until') != expected_openclaw_fresh_until:
            fail(f"expected openclaw fresh_until 2026-04-11T12:05:00Z, got {verified.get('openclaw')!r}")
        if verified.get('claude', {}).get('state') != 'unknown':
            fail(f"expected claude verified_support unknown, got {verified.get('claude')!r}")
        if verified.get('claude', {}).get('freshness_state') != 'unknown':
            fail(f"expected claude freshness_state unknown, got {verified.get('claude')!r}")
        if verified.get('claude', {}).get('freshness_reason') != 'missing-evidence':
            fail(f"expected claude freshness_reason missing-evidence, got {verified.get('claude')!r}")
        if verified.get('claude', {}).get('contract_last_verified') != claude_contract_day.isoformat():
            fail(f"expected claude contract_last_verified 2026-03-12, got {verified.get('claude')!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: compatibility evidence checks passed')


if __name__ == '__main__':
    main()
