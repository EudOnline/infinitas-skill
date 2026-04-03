#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.discovery.inspect import inspect_skill  # noqa: E402
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult  # noqa: E402

QUALIFIED_NAME = 'lvxiaoer/operate-infinitas-skill'
RELEASE_QUALIFIED_NAME = 'lvxiaoer/release-infinitas-skill'
CONSUME_QUALIFIED_NAME = 'lvxiaoer/consume-infinitas-skill'
FEDERATION_QUALIFIED_NAME = 'lvxiaoer/federation-registry-ops'


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
    for key in [
        'qualified_name',
        'publisher',
        'latest_version',
        'trust_state',
        'verified_support',
        'freshness_summary',
        'use_when',
        'avoid_when',
        'capabilities',
        'runtime_assumptions',
        'maturity',
        'quality_score',
    ]:
        if key not in match:
            fail(f'missing search field {key!r}')
    if match.get('use_when') != [
        'Need to operate inside the infinitas-skill repository',
        'Need guidance on registry workflows, planning files, or release discipline',
    ]:
        fail(f"expected canonical search use_when, got {match.get('use_when')!r}")
    if match.get('avoid_when') != ['Need a general-purpose Git helper outside this repository']:
        fail(f"expected canonical search avoid_when, got {match.get('avoid_when')!r}")
    if match.get('capabilities') != ['repo-operations', 'release-guidance', 'registry-debugging']:
        fail(f"expected canonical search capabilities, got {match.get('capabilities')!r}")
    if match.get('runtime_assumptions') != [
        'A Git checkout of infinitas-skill is available',
        'Repository scripts can be executed from the workspace',
    ]:
        fail(f"expected canonical search runtime_assumptions, got {match.get('runtime_assumptions')!r}")
    if match.get('maturity') != 'stable':
        fail(f"expected canonical search maturity 'stable', got {match.get('maturity')!r}")
    if match.get('quality_score') != 90:
        fail(f"expected canonical search quality_score 90, got {match.get('quality_score')!r}")


def scenario_search_filters_by_publisher_and_agent():
    result = run(['./scripts/search-skills.sh', '--publisher', 'lvxiaoer', '--agent', 'codex'], cwd=ROOT)
    payload = json.loads(result.stdout)
    results = payload.get('results') or []
    expected = {
        QUALIFIED_NAME,
        RELEASE_QUALIFIED_NAME,
        CONSUME_QUALIFIED_NAME,
        FEDERATION_QUALIFIED_NAME,
    }
    actual = {item.get('qualified_name') for item in results}
    missing = expected - actual
    if missing:
        fail(f'expected filtered results to include {sorted(missing)!r}, got {sorted(actual)!r}')
    for item in results:
        if item.get('publisher') != 'lvxiaoer':
            fail(f"unexpected publisher in filtered search result: {item.get('publisher')!r}")


def scenario_inspect_returns_distribution_and_dependency_views():
    result = run(['./scripts/inspect-skill.sh', QUALIFIED_NAME], cwd=ROOT)
    payload = json.loads(result.stdout)
    if payload.get('qualified_name') != QUALIFIED_NAME:
        fail(f"expected inspect qualified_name {QUALIFIED_NAME!r}, got {payload.get('qualified_name')!r}")
    for key in ['compatibility', 'dependencies', 'provenance', 'distribution', 'trust_state', 'decision_metadata']:
        if key not in payload:
            fail(f'missing inspect field {key!r}')
    compatibility = payload.get('compatibility') or {}
    verified_summary = compatibility.get('verified_summary') or {}
    if verified_summary.get('codex') != 'adapted':
        fail(f"expected codex compatibility summary 'adapted', got {verified_summary.get('codex')!r}")
    freshness_summary = compatibility.get('freshness_summary') or {}
    if freshness_summary.get('codex') not in {'fresh', 'stale', 'unknown'}:
        fail(f"expected codex freshness summary fresh/stale/unknown, got {freshness_summary.get('codex')!r}")
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
    decision_metadata = payload.get('decision_metadata') or {}
    if decision_metadata.get('use_when') != [
        'Need to operate inside the infinitas-skill repository',
        'Need guidance on registry workflows, planning files, or release discipline',
    ]:
        fail(f"expected inspect decision_metadata.use_when, got {decision_metadata.get('use_when')!r}")
    if decision_metadata.get('avoid_when') != ['Need a general-purpose Git helper outside this repository']:
        fail(f"expected inspect decision_metadata.avoid_when, got {decision_metadata.get('avoid_when')!r}")
    if decision_metadata.get('capabilities') != ['repo-operations', 'release-guidance', 'registry-debugging']:
        fail(f"expected inspect decision_metadata.capabilities, got {decision_metadata.get('capabilities')!r}")
    if decision_metadata.get('runtime_assumptions') != [
        'A Git checkout of infinitas-skill is available',
        'Repository scripts can be executed from the workspace',
    ]:
        fail(
            'expected inspect decision_metadata.runtime_assumptions, '
            f"got {decision_metadata.get('runtime_assumptions')!r}"
        )
    if decision_metadata.get('maturity') != 'stable':
        fail(f"expected inspect decision_metadata.maturity 'stable', got {decision_metadata.get('maturity')!r}")
    if decision_metadata.get('quality_score') != 90:
        fail(f"expected inspect decision_metadata.quality_score 90, got {decision_metadata.get('quality_score')!r}")


class FakeMemoryProvider:
    backend_name = 'fake'
    capabilities = {'read': True, 'write': True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(
            backend=self.backend_name,
            records=[
                MemoryRecord(
                    memory='OpenClaw installs usually succeed when the release is already materialized.',
                    memory_type='experience',
                    score=0.94,
                )
            ],
        )


def scenario_inspect_returns_memory_hints_without_changing_trust():
    payload = inspect_skill(
        ROOT,
        name=CONSUME_QUALIFIED_NAME,
        memory_provider=FakeMemoryProvider(),
        memory_scope={'user_ref': 'maintainer'},
    )
    memory_hints = payload.get('memory_hints') or {}
    if memory_hints.get('used') is not True:
        fail(f"expected memory_hints.used true, got {memory_hints.get('used')!r}")
    if memory_hints.get('backend') != 'fake':
        fail(f"expected memory_hints.backend 'fake', got {memory_hints.get('backend')!r}")
    if memory_hints.get('matched_count') != 1:
        fail(f"expected memory_hints.matched_count 1, got {memory_hints.get('matched_count')!r}")
    items = memory_hints.get('items') or []
    if not items or items[0].get('memory_type') != 'experience':
        fail(f'expected first memory hint type experience, got {items!r}')
    trust = payload.get('trust') or {}
    if payload.get('trust_state') != 'verified' or trust.get('state') != 'verified':
        fail(f"expected trust_state and trust.state to remain 'verified', got {payload.get('trust_state')!r} and {trust.get('state')!r}")


def main():
    scenario_search_returns_trust_and_compatibility_fields()
    scenario_search_filters_by_publisher_and_agent()
    scenario_inspect_returns_distribution_and_dependency_views()
    scenario_inspect_returns_memory_hints_without_changing_trust()
    print('OK: search and inspect checks passed')


if __name__ == '__main__':
    main()
