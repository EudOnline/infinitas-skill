#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_REL = Path('catalog/provenance/operate-infinitas-skill-0.1.1.json')
OPERATE_MANIFEST_REL = Path('catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json')


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


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_backfill(repo: Path, manifest_rel: Path):
    manifest_path = repo / manifest_rel
    if not manifest_path.exists():
        fail(f'missing manifest fixture for backfill: {manifest_path}')
    command = [
        sys.executable,
        str(repo / 'scripts' / 'backfill-distribution-manifests.py'),
        '--manifest',
        str(manifest_path),
        '--write',
        '--json',
    ]
    result = run(command, cwd=repo)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f'backfill command did not emit JSON:\n{result.stdout}\n{result.stderr}\n{exc}')
    if payload.get('state') != 'backfilled':
        fail(f"expected backfill to report state 'backfilled', got {payload!r}")


def inject_delegated_audit_fixture(repo: Path):
    provenance_path = repo / PROVENANCE_REL
    payload = load_json(provenance_path)
    payload['review'] = {
        'reviewers': [
            {
                'reviewer': 'lvxiaoer',
                'decision': 'approved',
                'at': '2026-03-12T12:14:51Z',
                'note': 'Fixture approval for export contract tests',
            }
        ],
        'effective_review_state': 'approved',
        'required_approvals': 1,
        'required_groups': ['maintainers'],
        'covered_groups': ['maintainers'],
        'missing_groups': [],
        'approval_count': 1,
        'blocking_rejection_count': 0,
        'quorum_met': True,
        'review_gate_pass': True,
        'latest_decisions': [
            {
                'reviewer': 'lvxiaoer',
                'decision': 'approved',
                'at': '2026-03-12T12:14:51Z',
            }
        ],
        'ignored_decisions': [],
        'configured_groups': {
            'maintainers': {
                'actors': ['lvxiaoer'],
                'teams': ['release-operators'],
            }
        },
    }
    payload['release'] = {
        **(payload.get('release') or {}),
        'delegated_teams': ['release-operators'],
        'exception_usage': [
            {
                'id': 'fixture-release-waiver',
                'matched_rules': ['dirty-worktree'],
                'approved_by': ['compliance-reviewer'],
                'justification': 'Fixture waiver for export coverage',
                'expires_at': '2099-01-01T00:00:00Z',
            }
        ],
    }
    write_json(provenance_path, payload)


def assert_inventory_export(repo: Path):
    export_path = repo / 'catalog' / 'inventory-export.json'
    if not export_path.exists():
        fail(f'missing inventory export: {export_path}')

    payload = load_json(export_path)
    if payload.get('schema_version') != 1:
        fail(f"expected inventory export schema_version 1, got {payload.get('schema_version')!r}")
    if payload.get('default_registry') != 'self':
        fail(f"expected inventory export default_registry 'self', got {payload.get('default_registry')!r}")

    registries = payload.get('registries') or []
    self_registry = next((item for item in registries if item.get('name') == 'self'), None)
    if self_registry is None:
        fail(f'expected self registry export, got {registries!r}')
    if self_registry.get('resolver_candidate') is not True:
        fail(f"expected self registry resolver_candidate true, got {self_registry!r}")

    skills = payload.get('skills') or []
    skill = next((item for item in skills if item.get('qualified_name') == 'lvxiaoer/operate-infinitas-skill'), None)
    if skill is None:
        fail(f'expected inventory export skill entry, got {skills!r}')
    if skill.get('source_registry') != 'self':
        fail(f"expected source_registry 'self', got {skill!r}")
    if skill.get('source_registry_trust') != 'private':
        fail(f"expected source_registry_trust 'private', got {skill!r}")
    if skill.get('installable') is not True:
        fail(f'expected installable skill export, got {skill!r}')
    if skill.get('released') is not True:
        fail(f'expected released skill export, got {skill!r}')
    if skill.get('release_attestation_path') != str(PROVENANCE_REL):
        fail(f"expected release_attestation_path {str(PROVENANCE_REL)!r}, got {skill!r}")
    if skill.get('release_installed_integrity_capability') != 'supported':
        fail(
            "expected inventory export release_installed_integrity_capability 'supported', "
            f'got {skill!r}'
        )
    if skill.get('release_installed_integrity_reason') is not None:
        fail(f'expected inventory export release_installed_integrity_reason to be omitted, got {skill!r}')


def _distribution_by_key(entries, *, qualified_name: str, version: str):
    for item in entries or []:
        if not isinstance(item, dict):
            continue
        if item.get('qualified_name') == qualified_name and item.get('version') == version:
            return item
    return None


def assert_integrity_capability_surfaces(repo: Path):
    distributions_path = repo / 'catalog' / 'distributions.json'
    if not distributions_path.exists():
        fail(f'missing distributions index: {distributions_path}')
    distributions = load_json(distributions_path)
    dist_entries = distributions.get('skills') or []

    operate = _distribution_by_key(dist_entries, qualified_name='lvxiaoer/operate-infinitas-skill', version='0.1.1')
    if operate is None:
        fail(f'missing operate distribution entry in distributions.json, got {dist_entries!r}')
    if operate.get('installed_integrity_capability') != 'supported':
        fail(f"expected operate installed_integrity_capability 'supported', got {operate!r}")
    if operate.get('installed_integrity_reason') is not None:
        fail(f'expected operate installed_integrity_reason to be omitted, got {operate!r}')
    if not isinstance(operate.get('file_manifest_count'), int) or operate.get('file_manifest_count') < 1:
        fail(f'expected operate file_manifest_count to be a positive integer, got {operate!r}')

    legacy = _distribution_by_key(dist_entries, qualified_name='lvxiaoer/federation-registry-ops', version='0.1.0')
    if legacy is None:
        fail(f'missing legacy distribution entry in distributions.json, got {dist_entries!r}')
    if legacy.get('installed_integrity_capability') != 'unknown':
        fail(f"expected legacy installed_integrity_capability 'unknown', got {legacy!r}")
    if legacy.get('installed_integrity_reason') != 'missing-signed-file-manifest':
        fail(f"expected legacy installed_integrity_reason 'missing-signed-file-manifest', got {legacy!r}")

    catalog_path = repo / 'catalog' / 'catalog.json'
    if not catalog_path.exists():
        fail(f'missing catalog export: {catalog_path}')
    catalog = load_json(catalog_path)
    skills = catalog.get('skills') or []
    operate_skill = next((item for item in skills if item.get('qualified_name') == 'lvxiaoer/operate-infinitas-skill'), None)
    if operate_skill is None:
        fail(f'missing operate skill entry in catalog.json, got {skills!r}')
    verified_distribution = operate_skill.get('verified_distribution') or {}
    if verified_distribution.get('installed_integrity_capability') != 'supported':
        fail(f"expected catalog verified_distribution installed_integrity_capability 'supported', got {operate_skill!r}")
    if verified_distribution.get('installed_integrity_reason') is not None:
        fail(f'expected catalog verified_distribution installed_integrity_reason to be omitted, got {operate_skill!r}')

    discovery_guidance = (
        repo / 'docs' / 'reference' / 'distribution-manifests.md'
    ).read_text(encoding='utf-8')
    if 'installed_integrity_capability' not in discovery_guidance:
        fail("expected docs/reference/distribution-manifests.md to mention 'installed_integrity_capability'")


def assert_audit_export(repo: Path):
    export_path = repo / 'catalog' / 'audit-export.json'
    if not export_path.exists():
        fail(f'missing audit export: {export_path}')

    payload = load_json(export_path)
    if payload.get('schema_version') != 1:
        fail(f"expected audit export schema_version 1, got {payload.get('schema_version')!r}")

    releases = payload.get('releases') or []
    release = next(
        (
            item for item in releases
            if item.get('qualified_name') == 'lvxiaoer/operate-infinitas-skill' and item.get('version') == '0.1.1'
        ),
        None,
    )
    if release is None:
        fail(f'expected audit export release entry, got {releases!r}')
    if release.get('provenance_path') != str(PROVENANCE_REL):
        fail(f"expected provenance_path {str(PROVENANCE_REL)!r}, got {release!r}")

    source_snapshot = release.get('source_snapshot') or {}
    if source_snapshot.get('tag') != 'skill/operate-infinitas-skill/v0.1.1':
        fail(f"expected immutable source snapshot tag, got {release!r}")

    review = release.get('review') or {}
    if review.get('effective_review_state') != 'approved':
        fail(f"expected effective_review_state 'approved', got {review!r}")

    release_info = release.get('release') or {}
    if release_info.get('delegated_teams') != ['release-operators']:
        fail(f"expected delegated_teams ['release-operators'], got {release_info!r}")
    exception_usage = release_info.get('exception_usage') or []
    if not exception_usage or exception_usage[0].get('id') != 'fixture-release-waiver':
        fail(f'expected fixture exception usage in audit export, got {release_info!r}')

    for forbidden in ['integrity', 'installed_integrity', 'installed_state', 'installed_runtime']:
        if forbidden in release:
            fail(f'expected audit-export release entry not to include {forbidden!r}, got {release!r}')


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-audit-inventory-export-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    # Ensure at least one distribution manifest carries the released-file inventory so
    # release surfaces can report installed-integrity capability as "supported".
    run_backfill(repo, OPERATE_MANIFEST_REL)
    inject_delegated_audit_fixture(repo)
    return tmpdir, repo


def main():
    tmpdir, repo = prepare_repo()
    try:
        run(['bash', 'scripts/build-catalog.sh'], cwd=repo)
        assert_inventory_export(repo)
        assert_integrity_capability_surfaces(repo)
        assert_audit_export(repo)
    finally:
        shutil.rmtree(tmpdir)

    print('OK: audit inventory export checks passed')


if __name__ == '__main__':
    main()
