#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from result_schema_lib import validate_publish_result, validate_pull_result


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


def read(path: Path) -> str:
    if not path.exists():
        fail(f'missing required file: {path}')
    return path.read_text(encoding='utf-8')


def assert_contains(path: Path, needle: str):
    content = read(path)
    if needle not in content:
        fail(f'expected {path} to mention {needle!r}')


def load_stdout_json(command):
    result = run(command, cwd=ROOT)
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'could not parse JSON from {command!r}: {exc}\nstdout:\n{result.stdout}')


def scenario_docs_define_public_workflow_surface():
    workflow_doc = ROOT / 'docs' / 'ai' / 'workflow-drills.md'
    agent_ops = ROOT / 'docs' / 'ai' / 'agent-operations.md'

    assert_contains(agent_ops, 'docs/ai/workflow-drills.md')
    assert_contains(agent_ops, 'implementation internals')
    assert_contains(workflow_doc, 'scripts/search-skills.sh')
    assert_contains(workflow_doc, 'scripts/recommend-skill.sh')
    assert_contains(workflow_doc, 'scripts/inspect-skill.sh')
    assert_contains(workflow_doc, 'scripts/publish-skill.sh')
    assert_contains(workflow_doc, 'scripts/pull-skill.sh')
    assert_contains(workflow_doc, '--mode confirm')


def scenario_search_recommend_inspect_drill():
    search_payload = load_stdout_json(['scripts/search-skills.sh', 'release'])
    results = search_payload.get('results') or []
    if not results:
        fail(f'expected search drill results, got {search_payload!r}')
    top = results[0]
    if top.get('qualified_name') != 'lvxiaoer/release-infinitas-skill':
        fail(f'unexpected top search result {top!r}')
    for key in ['use_when', 'runtime_assumptions', 'verified_support']:
        if not top.get(key):
            fail(f'expected search drill top result to expose {key}, got {top!r}')

    recommend_payload = load_stdout_json(['scripts/recommend-skill.sh', 'publish immutable skill release'])
    rec_results = recommend_payload.get('results') or []
    if not rec_results:
        fail(f'expected recommendation drill results, got {recommend_payload!r}')
    winner = rec_results[0]
    if winner.get('qualified_name') != 'lvxiaoer/release-infinitas-skill':
        fail(f'unexpected recommendation winner {winner!r}')
    if not winner.get('recommendation_reason'):
        fail(f'missing recommendation_reason in workflow drill output {winner!r}')
    if not winner.get('ranking_factors'):
        fail(f'missing ranking_factors in workflow drill output {winner!r}')

    inspect_payload = load_stdout_json(['scripts/inspect-skill.sh', 'lvxiaoer/release-infinitas-skill'])
    if inspect_payload.get('qualified_name') != 'lvxiaoer/release-infinitas-skill':
        fail(f'unexpected inspect drill payload {inspect_payload!r}')
    decision = inspect_payload.get('decision_metadata') or {}
    if not decision.get('use_when'):
        fail(f'expected inspect drill decision metadata, got {inspect_payload!r}')
    distribution = inspect_payload.get('distribution') or {}
    if not distribution.get('manifest_path'):
        fail(f'expected inspect drill distribution manifest path, got {inspect_payload!r}')
    provenance = inspect_payload.get('provenance') or {}
    if not provenance.get('attestation_path'):
        fail(f'expected inspect drill provenance path, got {inspect_payload!r}')


def scenario_publish_pull_confirm_drill():
    publish_payload = load_stdout_json(['scripts/publish-skill.sh', 'release-infinitas-skill', '--mode', 'confirm'])
    publish_errors = validate_publish_result(publish_payload)
    if publish_errors:
        fail('publish drill schema errors:\n' + '\n'.join(publish_errors))
    if publish_payload.get('state') != 'planned':
        fail(f"expected planned publish drill output, got {publish_payload!r}")
    if publish_payload.get('next_step') != 'confirm-or-run':
        fail(f"expected publish next_step confirm-or-run, got {publish_payload!r}")
    commands = publish_payload.get('commands') or []
    if not commands:
        fail(f'expected publish drill commands, got {publish_payload!r}')

    temp_root = Path(tempfile.mkdtemp(prefix='infinitas-ai-workflow-drill-'))
    try:
        target_dir = temp_root / 'installed'
        pull_payload = load_stdout_json(
            ['scripts/pull-skill.sh', 'lvxiaoer/release-infinitas-skill', str(target_dir), '--mode', 'confirm']
        )
        pull_errors = validate_pull_result(pull_payload)
        if pull_errors:
            fail('pull drill schema errors:\n' + '\n'.join(pull_errors))
        if pull_payload.get('state') != 'planned':
            fail(f"expected planned pull drill output, got {pull_payload!r}")
        if pull_payload.get('next_step') != 'confirm-or-run':
            fail(f"expected pull next_step confirm-or-run, got {pull_payload!r}")
        for key in ['manifest_path', 'attestation_path', 'install_command', 'explanation']:
            if not pull_payload.get(key):
                fail(f'expected pull drill to expose {key}, got {pull_payload!r}')
    finally:
        shutil.rmtree(temp_root)


def main():
    scenario_docs_define_public_workflow_surface()
    scenario_search_recommend_inspect_drill()
    scenario_publish_pull_confirm_drill()
    print('OK: ai workflow drill checks passed')


if __name__ == '__main__':
    main()
