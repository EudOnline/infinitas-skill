#!/usr/bin/env python3
import sys


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


try:
    from decision_metadata_lib import canonical_decision_metadata  # noqa: E402
except Exception as exc:
    fail(f'could not import decision_metadata_lib: {exc}')


def scenario_normalizes_source_metadata():
    payload = canonical_decision_metadata(
        {
            'use_when': [' Need repo operations ', '', 42, 'Need release guidance'],
            'avoid_when': ['   ', 'Need public marketplace publishing'],
            'capabilities': [' repo-operations ', None, 'release-guidance'],
            'runtime_assumptions': [' Git checkout available ', '', 'Repository scripts executable'],
            'maturity': ' stable ',
            'quality_score': 90,
        }
    )
    if payload != {
        'use_when': ['Need repo operations', 'Need release guidance'],
        'avoid_when': ['Need public marketplace publishing'],
        'capabilities': ['repo-operations', 'release-guidance'],
        'runtime_assumptions': ['Git checkout available', 'Repository scripts executable'],
        'maturity': 'stable',
        'quality_score': 90,
    }:
        fail(f'unexpected normalized source metadata {payload!r}')


def scenario_projects_generated_entry_fields():
    payload = canonical_decision_metadata(
        {
            'use_when': ['Need immutable install'],
            'avoid_when': ['Need mutable prototype copy'],
            'capabilities': ['immutable-install'],
            'runtime_assumptions': ['Release artifacts are available'],
            'maturity': 'beta',
            'quality_score': 'not-an-int',
        }
    )
    if payload.get('quality_score') != 0:
        fail(f"expected fallback quality_score 0, got {payload.get('quality_score')!r}")
    if payload.get('maturity') != 'beta':
        fail(f"expected beta maturity, got {payload.get('maturity')!r}")


def scenario_applies_stable_defaults():
    payload = canonical_decision_metadata({})
    if payload != {
        'use_when': [],
        'avoid_when': [],
        'capabilities': [],
        'runtime_assumptions': [],
        'maturity': 'unknown',
        'quality_score': 0,
    }:
        fail(f'unexpected default decision metadata {payload!r}')


def main():
    scenario_normalizes_source_metadata()
    scenario_projects_generated_entry_fields()
    scenario_applies_stable_defaults()
    print('OK: decision metadata helper checks passed')


if __name__ == '__main__':
    main()
