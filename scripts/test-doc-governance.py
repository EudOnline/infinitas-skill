#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / 'docs'
REQUIRED_FIELDS = ['audience', 'owner', 'source_of_truth', 'last_reviewed', 'status']
BAD_LINK_PATTERN = re.compile(r'/Users/.+?/\.worktrees/')
LEGACY_ROOT_ALLOWLIST = {
    'README.md',
    'project-closeout.md',
    'registry-snapshot-mirrors.md',
    'release-strategy.md',
}
SECTION_LANDINGS = {
    'guide': DOCS_ROOT / 'guide' / 'README.md',
    'reference': DOCS_ROOT / 'reference' / 'README.md',
    'ops': DOCS_ROOT / 'ops' / 'README.md',
    'archive': DOCS_ROOT / 'archive' / 'README.md',
}
GLOBAL_INDEXES = [ROOT / 'README.md', DOCS_ROOT / 'README.md']
MAINTAINED_SURFACE_DOCS = {
    ROOT / 'README.md',
    DOCS_ROOT / 'guide' / 'maintainability-reset-policy.md',
    DOCS_ROOT / 'reference' / 'cli-command-map.md',
    DOCS_ROOT / 'reference' / 'cli-reference.md',
    DOCS_ROOT / 'ops' / 'release-checklist.md',
}
REQUIRED_MAINTAINED_SURFACE_MARKERS = [
    '## Maintained surfaces',
    'package-owned:',
    'runtime-owned:',
    'compatibility-only:',
]
LEGACY_CANONICAL_ENTRYPOINTS = {
    'scripts/check-platform-contracts.py': 'infinitas compatibility check-platform-contracts',
    'scripts/resolve-install-plan.py': 'infinitas install resolve-plan',
    'scripts/check-install-target.py': 'infinitas install check-target',
    'scripts/check-policy-packs.py': 'infinitas policy check-packs',
    'scripts/check-promotion-policy.py': 'infinitas policy check-promotion',
    'scripts/registryctl.py': 'infinitas registry',
    'scripts/check-release-state.py': 'infinitas release check-state',
    'scripts/server-healthcheck.py': 'infinitas server healthcheck',
    'scripts/backup-hosted-registry.py': 'infinitas server backup',
    'scripts/inspect-hosted-state.py': 'infinitas server inspect-state',
    'scripts/render-hosted-systemd.py': 'infinitas server render-systemd',
    'scripts/prune-hosted-backups.py': 'infinitas server prune-backups',
    'scripts/run-hosted-worker.py': 'infinitas server worker',
}


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def parse_front_matter(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != '---':
        return None

    metadata = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == '---':
            return metadata
        if ':' not in stripped:
            fail(f'invalid front matter line in {path}: {line!r}')
        key, value = stripped.split(':', 1)
        metadata[key.strip()] = value.strip()

    fail(f'missing front matter end marker in {path}')


def all_doc_paths():
    paths = [ROOT / 'README.md']
    for path in DOCS_ROOT.rglob('*.md'):
        if 'plans' in path.parts:
            continue
        paths.append(path)
    return sorted(paths)


def maintained_docs():
    docs = []
    for path in all_doc_paths():
        metadata = parse_front_matter(path)
        if metadata and metadata.get('status') == 'maintained':
            docs.append((path, metadata))
    return docs


def check_root_allowlist():
    root_docs = {path.name for path in DOCS_ROOT.glob('*.md')}
    unexpected = sorted(root_docs - LEGACY_ROOT_ALLOWLIST)
    if unexpected:
        fail(f'unexpected root docs outside governance allowlist: {unexpected!r}')


def ensure_allowed_location(path: Path):
    if path == ROOT / 'README.md' or path == DOCS_ROOT / 'README.md':
        return
    if path.is_relative_to(DOCS_ROOT / 'guide'):
        return
    if path.is_relative_to(DOCS_ROOT / 'reference'):
        return
    if path.is_relative_to(DOCS_ROOT / 'ops'):
        return
    if path.is_relative_to(DOCS_ROOT / 'archive'):
        return
    if path.is_relative_to(DOCS_ROOT / 'adr'):
        return
    fail(f'maintained doc is outside allowed governance locations: {path}')


def ensure_required_metadata(path: Path, metadata: dict[str, str]):
    for field in REQUIRED_FIELDS:
        if not metadata.get(field):
            fail(f'missing required metadata field {field!r} in {path}')


def linked_from_any(path: Path, sources: list[Path]):
    basename = path.name
    for source in sources:
        if not source.exists():
            continue
        text = source.read_text(encoding='utf-8')
        if basename in text:
            return True
    return False


def ensure_landing_coverage(path: Path):
    if path in GLOBAL_INDEXES:
        return
    if path.name == 'README.md':
        return
    if path.is_relative_to(DOCS_ROOT / 'adr'):
        if not linked_from_any(path, GLOBAL_INDEXES):
            fail(f'maintained ADR is not linked from a global index: {path}')
        return

    for section, landing in SECTION_LANDINGS.items():
        section_root = DOCS_ROOT / section
        if path.is_relative_to(section_root):
            if not linked_from_any(path, [landing]):
                fail(f'maintained doc is not linked from its section landing page: {path}')
            return


def ensure_no_worktree_links(path: Path):
    text = path.read_text(encoding='utf-8')
    if BAD_LINK_PATTERN.search(text):
        fail(f'maintained doc must not contain absolute worktree links: {path}')


def ensure_readme_has_maintained_surface_inventory():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    for marker in REQUIRED_MAINTAINED_SURFACE_MARKERS:
        if marker not in text:
            fail(f'missing maintained surface inventory marker {marker!r} in README.md')


def ensure_legacy_command_mentions_have_canonical_entrypoints(path: Path):
    if path not in MAINTAINED_SURFACE_DOCS:
        return

    text = path.read_text(encoding='utf-8')
    for legacy_marker, canonical_entrypoint in LEGACY_CANONICAL_ENTRYPOINTS.items():
        if legacy_marker in text and canonical_entrypoint not in text:
            fail(
                'maintained surface doc mentions legacy command '
                f'{legacy_marker!r} without canonical entrypoint '
                f'{canonical_entrypoint!r}: {path}'
            )


def main():
    check_root_allowlist()
    docs = maintained_docs()
    if not docs:
        fail('expected at least one maintained document')

    ensure_readme_has_maintained_surface_inventory()

    for path, metadata in docs:
        ensure_allowed_location(path)
        ensure_required_metadata(path, metadata)
        ensure_landing_coverage(path)
        ensure_no_worktree_links(path)
        ensure_legacy_command_mentions_have_canonical_entrypoints(path)

    print('OK: document governance checks passed')


if __name__ == '__main__':
    main()
