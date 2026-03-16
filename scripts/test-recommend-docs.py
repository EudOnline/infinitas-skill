#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f'missing documentation file: {path}')
    return path.read_text(encoding='utf-8')


def assert_contains(path: Path, needle: str):
    content = read(path)
    if needle not in content:
        fail(f'expected {path} to mention {needle!r}')


def main():
    readme = ROOT / 'README.md'
    discovery = ROOT / 'docs' / 'ai' / 'discovery.md'
    search_doc = ROOT / 'docs' / 'ai' / 'search-and-inspect.md'
    recommend_doc = ROOT / 'docs' / 'ai' / 'recommend.md'
    workflow_doc = ROOT / 'docs' / 'ai' / 'workflow-drills.md'

    assert_contains(readme, 'scripts/recommend-skill.sh')
    assert_contains(readme, 'docs/ai/workflow-drills.md')
    assert_contains(discovery, 'scripts/recommend-skill.sh')
    assert_contains(search_doc, 'scripts/recommend-skill.sh')
    assert_contains(search_doc, 'search-skills.sh')
    assert_contains(search_doc, 'inspect-skill.sh')
    assert_contains(search_doc, 'recommendation_reason')
    assert_contains(search_doc, 'ranking_factors')
    assert_contains(search_doc, 'confidence')
    assert_contains(search_doc, 'comparative_signals')
    assert_contains(recommend_doc, 'scripts/recommend-skill.sh')
    assert_contains(recommend_doc, 'trust state')
    assert_contains(recommend_doc, 'compatibility')
    assert_contains(recommend_doc, 'maturity')
    assert_contains(recommend_doc, 'verification freshness')
    assert_contains(recommend_doc, 'confidence')
    assert_contains(recommend_doc, 'comparative_signals')
    assert_contains(recommend_doc, 'comparison_summary')
    assert_contains(recommend_doc, '_meta.json')
    assert_contains(recommend_doc, 'canonical source')
    assert_contains(workflow_doc, 'scripts/recommend-skill.sh')
    assert_contains(workflow_doc, 'scripts/inspect-skill.sh')
    assert_contains(workflow_doc, '--mode confirm')

    print('OK: recommend docs checks passed')


if __name__ == '__main__':
    main()
