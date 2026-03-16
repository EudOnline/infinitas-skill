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
    pull = ROOT / 'docs' / 'ai' / 'pull.md'
    operations = ROOT / 'docs' / 'ai' / 'agent-operations.md'
    search_doc = ROOT / 'docs' / 'ai' / 'search-and-inspect.md'
    workflow_doc = ROOT / 'docs' / 'ai' / 'workflow-drills.md'
    usage_guide = ROOT / 'docs' / 'ai' / 'usage-guide.md'

    assert_contains(readme, 'scripts/search-skills.sh')
    assert_contains(readme, 'docs/ai/workflow-drills.md')
    assert_contains(readme, 'docs/ai/usage-guide.md')
    assert_contains(readme, 'scripts/inspect-skill.sh')
    assert_contains(discovery, 'scripts/search-skills.sh')
    assert_contains(discovery, 'scripts/install-by-name.sh')
    assert_contains(discovery, 'explanation')
    assert_contains(pull, 'verified distribution manifests')
    assert_contains(pull, 'trust state')
    assert_contains(operations, 'docs/ai/usage-guide.md')
    assert_contains(operations, 'scripts/inspect-skill.sh')
    assert_contains(operations, 'scripts/search-skills.sh')
    assert_contains(operations, 'provenance')
    assert_contains(operations, 'docs/ai/workflow-drills.md')
    assert_contains(operations, 'implementation internals')
    assert_contains(search_doc, 'scripts/search-skills.sh')
    assert_contains(search_doc, 'scripts/inspect-skill.sh')
    assert_contains(search_doc, 'verified distribution manifests')
    assert_contains(search_doc, 'compatibility')
    assert_contains(search_doc, 'trust state')
    assert_contains(search_doc, 'provenance')
    assert_contains(search_doc, 'install-by-name.sh')
    assert_contains(search_doc, 'upgrade-skill.sh')
    assert_contains(workflow_doc, 'scripts/search-skills.sh')
    assert_contains(workflow_doc, 'scripts/inspect-skill.sh')
    assert_contains(workflow_doc, 'scripts/pull-skill.sh')
    assert_contains(workflow_doc, '--mode confirm')
    assert_contains(usage_guide, 'scripts/search-skills.sh')
    assert_contains(usage_guide, 'scripts/publish-skill.sh')

    print('OK: search docs checks passed')


if __name__ == '__main__':
    main()
