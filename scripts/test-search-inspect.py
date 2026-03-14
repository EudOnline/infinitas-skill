#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
QUALIFIED_NAME = 'lvxiaoer/operate-infinitas-skill'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError as exc:
        fail(f'missing command {command[0]!r}: {exc}')
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def scenario_search_returns_trust_and_compatibility_fields():
    result = run(['./scripts/search-skills.sh', 'operate'], cwd=ROOT)
    payload = json.loads(result.stdout)
    results = payload.get('results') or []
    if not results:
        fail('expected at least one search result')
    match = next((item for item in results if item.get('qualified_name') == QUALIFIED_NAME), None)
    if match is None:
        fail(f'expected search results to include {QUALIFIED_NAME!r}')
    for key in ['qualified_name', 'publisher', 'latest_version', 'trust_state', 'verified_support']:
        if key not in match:
            fail(f'missing search field {key!r}')


def scenario_search_filters_by_publisher_and_agent():
    result = run(['./scripts/search-skills.sh', '--publisher', 'lvxiaoer', '--agent', 'codex'], cwd=ROOT)
    payload = json.loads(result.stdout)
    results = payload.get('results') or []
    if len(results) != 1:
        fail(f'expected exactly one filtered result, got {len(results)}')
    if results[0].get('qualified_name') != QUALIFIED_NAME:
        fail(f"unexpected filtered result {results[0].get('qualified_name')!r}")


def scenario_inspect_returns_distribution_and_dependency_views():
    result = run(['./scripts/inspect-skill.sh', QUALIFIED_NAME], cwd=ROOT)
    payload = json.loads(result.stdout)
    if payload.get('qualified_name') != QUALIFIED_NAME:
        fail(f"expected inspect qualified_name {QUALIFIED_NAME!r}, got {payload.get('qualified_name')!r}")
    for key in ['compatibility', 'dependencies', 'provenance', 'distribution', 'trust_state']:
        if key not in payload:
            fail(f'missing inspect field {key!r}')
    compatibility = payload.get('compatibility') or {}
    verified_summary = compatibility.get('verified_summary') or {}
    if verified_summary.get('codex') != 'adapted':
        fail(f"expected codex compatibility summary 'adapted', got {verified_summary.get('codex')!r}")
    dependencies = payload.get('dependencies') or {}
    summary = dependencies.get('summary') or {}
    if summary.get('root_name') != 'operate-infinitas-skill':
        fail(f"expected dependency root_name 'operate-infinitas-skill', got {summary.get('root_name')!r}")
    if summary.get('root_source_type') != 'working-tree':
        fail(f"expected dependency root_source_type 'working-tree', got {summary.get('root_source_type')!r}")
    if summary.get('step_count', 0) < 1:
        fail(f"expected dependency step_count >= 1, got {summary.get('step_count')!r}")
    provenance = payload.get('provenance') or {}
    if not provenance.get('release_provenance_path'):
        fail('expected release_provenance_path in inspect provenance view')
    if provenance.get('required_attestation_formats') != ['ssh']:
        fail(f"expected required_attestation_formats ['ssh'], got {provenance.get('required_attestation_formats')!r}")
    policy = provenance.get('policy') or {}
    if policy.get('require_verified_attestation_for_distribution') is not True:
        fail('expected inspect provenance policy to require verified attestation for distribution')
    distribution = payload.get('distribution') or {}
    if distribution.get('source_type') != 'distribution-manifest':
        fail(f"expected distribution source_type 'distribution-manifest', got {distribution.get('source_type')!r}")
    trust = payload.get('trust') or {}
    if trust.get('state') != 'verified':
        fail(f"expected inspect trust.state 'verified', got {trust.get('state')!r}")
    if trust.get('signature_present') is not True:
        fail(f"expected inspect trust.signature_present true, got {trust.get('signature_present')!r}")


def main():
    scenario_search_returns_trust_and_compatibility_fields()
    scenario_search_filters_by_publisher_and_agent()
    scenario_inspect_returns_distribution_and_dependency_views()
    print('OK: search and inspect checks passed')


if __name__ == '__main__':
    main()
