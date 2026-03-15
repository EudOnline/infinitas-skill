#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

from policy_pack_lib import PolicyPackError, load_effective_policy_domain, load_policy_domain_resolution


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def base_selector():
    return {
        '$schema': '../schemas/policy-pack-selection.schema.json',
        'version': 1,
        'compatibility_version': '11-01',
        'description': 'Fixture selector for policy-pack loading tests',
        'active_packs': ['baseline', 'dual-attestation'],
    }


def baseline_pack():
    return {
        '$schema': '../../schemas/policy-pack.schema.json',
        'schema_version': 1,
        'name': 'baseline',
        'description': 'Baseline policy defaults',
        'domains': {
            'promotion_policy': {
                'version': 4,
                'active_requires': {
                    'review_state': ['approved'],
                    'require_changelog': True,
                    'require_smoke_test': True,
                    'require_owner': True,
                },
                'reviews': {
                    'require_reviews_file': True,
                    'reviewer_must_differ_from_owner': True,
                    'allow_owner_when_no_distinct_reviewer': True,
                    'block_on_rejection': True,
                    'groups': {
                        'maintainers': {
                            'members': ['pack-maintainer'],
                        }
                    },
                    'quorum': {
                        'defaults': {
                            'min_approvals': 1,
                            'required_groups': [],
                        },
                        'stage_overrides': {
                            'active': {
                                'min_approvals': 1,
                                'required_groups': ['maintainers'],
                            }
                        },
                    },
                },
            },
            'namespace_policy': {
                'version': 1,
                'compatibility': {
                    'allow_unqualified_names': False,
                },
                'publishers': {
                    'baseline': {
                        'owners': ['pack-owner'],
                    }
                },
                'transfers': [],
            },
            'signing': {
                'namespace': 'infinitas-skill',
                'allowed_signers': 'config/allowed_signers',
                'signature_ext': '.ssig',
                'git_tag': {
                    'format': 'ssh',
                    'allowed_signers': 'config/allowed_signers',
                    'remote': 'origin',
                    'signing_key_env': 'INFINITAS_SKILL_GIT_SIGNING_KEY',
                },
                'attestation': {
                    'format': 'ssh',
                    'namespace': 'infinitas-skill',
                    'allowed_signers': 'config/allowed_signers',
                    'signature_ext': '.ssig',
                    'signing_key_env': 'INFINITAS_SKILL_GIT_SIGNING_KEY',
                    'policy': {
                        'mode': 'enforce',
                        'release_trust_mode': 'ssh',
                        'require_verified_attestation_for_release_output': True,
                        'require_verified_attestation_for_distribution': True,
                    },
                },
            },
            'registry_sources': {
                'default_registry': 'baseline',
                'registries': [
                    {
                        'name': 'baseline',
                        'kind': 'git',
                        'url': 'https://example.invalid/baseline.git',
                        'priority': 50,
                        'enabled': True,
                        'trust': 'trusted',
                        'allowed_hosts': ['example.invalid'],
                        'allowed_refs': ['refs/heads/main'],
                        'pin': {
                            'mode': 'branch',
                            'value': 'main',
                        },
                        'update_policy': {
                            'mode': 'track',
                        },
                    }
                ],
            },
        },
    }


def dual_attestation_pack():
    return {
        '$schema': '../../schemas/policy-pack.schema.json',
        'schema_version': 1,
        'name': 'dual-attestation',
        'description': 'Overrides baseline signing policy',
        'domains': {
            'signing': {
                'attestation': {
                    'ci': {
                        'provider': 'github-actions',
                        'repository': 'lvxiaoer/infinitas-skill',
                        'workflow': 'release-attestation',
                    },
                    'policy': {
                        'release_trust_mode': 'both',
                    },
                },
            },
            'namespace_policy': {
                'publishers': {
                    'dual': {
                        'owners': ['dual-owner'],
                        'maintainers': ['dual-maintainer'],
                    }
                }
            },
            'team_policy': {
                'version': 1,
                'teams': {
                    'release-operators': {
                        'members': ['dual-release'],
                    }
                },
            },
            'exception_policy': {
                'version': 1,
                'exceptions': [
                    {
                        'id': 'pack-release-waiver',
                        'scope': 'release',
                        'skills': ['pack/fixture'],
                        'rules': ['dirty-worktree'],
                        'approved_by': ['pack-approver'],
                        'approved_at': '2026-03-15T00:00:00Z',
                        'justification': 'Fixture pack exception',
                        'expires_at': '2099-01-01T00:00:00Z',
                    }
                ],
            },
        },
    }


def repo_local_promotion_override():
    return {
        '$schema': '../schemas/promotion-policy.schema.json',
        'version': 4,
        'reviews': {
            'groups': {
                'security': {
                    'members': ['repo-security'],
                }
            },
            'quorum': {
                'stage_overrides': {
                    'active': {
                        'required_groups': ['maintainers', 'security'],
                    }
                }
            },
        },
    }


def repo_local_signing_override():
    return {
        '$schema': '../schemas/signing.schema.json',
        'attestation': {
            'policy': {
                'release_trust_mode': 'ci',
            }
        },
    }


def repo_local_team_override():
    return {
        '$schema': '../schemas/team-policy.schema.json',
        'version': 1,
        'teams': {
            'platform-admins': {
                'members': ['repo-admin'],
            }
        },
    }


def repo_local_exception_override():
    return {
        '$schema': '../schemas/exception-policy.schema.json',
        'version': 1,
        'exceptions': [
            {
                'id': 'repo-promotion-waiver',
                'scope': 'promotion',
                'skills': ['repo-fixture'],
                'rules': ['required-reviewer-groups'],
                'approved_by': ['repo-approver'],
                'approved_at': '2026-03-15T00:05:00Z',
                'justification': 'Repository-local fixture exception',
                'expires_at': '2099-01-02T00:00:00Z',
            }
        ],
    }


def make_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-policy-pack-loading-'))
    repo = tmpdir / 'repo'
    try:
        write_json(repo / 'policy' / 'policy-packs.json', base_selector())
        write_json(repo / 'policy' / 'packs' / 'baseline.json', baseline_pack())
        write_json(repo / 'policy' / 'packs' / 'dual-attestation.json', dual_attestation_pack())
        write_json(repo / 'policy' / 'promotion-policy.json', repo_local_promotion_override())
        write_json(repo / 'policy' / 'exception-policy.json', repo_local_exception_override())
        write_json(repo / 'policy' / 'team-policy.json', repo_local_team_override())
        write_json(repo / 'config' / 'signing.json', repo_local_signing_override())
        (repo / 'config' / 'allowed_signers').write_text('# fixture\n', encoding='utf-8')
        return tmpdir, repo
    except Exception:
        shutil.rmtree(tmpdir)
        raise


def scenario_declared_pack_order_and_local_overrides():
    tmpdir, repo = make_repo()
    try:
        resolution = load_policy_domain_resolution(repo, 'signing')
        sources = resolution.get('effective_sources') or []
        if [item.get('kind') for item in sources] != ['pack', 'pack', 'local_override']:
            fail(f'unexpected policy source order: {sources!r}')
        if [item.get('name') for item in sources[:2]] != ['baseline', 'dual-attestation']:
            fail(f'unexpected pack source names: {sources!r}')
        if sources[-1].get('path') != 'config/signing.json':
            fail(f"expected local override path 'config/signing.json', got {sources[-1].get('path')!r}")

        effective_signing = load_effective_policy_domain(repo, 'signing')
        policy = ((effective_signing.get('attestation') or {}).get('policy') or {})
        if policy.get('release_trust_mode') != 'ci':
            fail(f"expected repo-local signing override to win, got {policy.get('release_trust_mode')!r}")
        ci = ((effective_signing.get('attestation') or {}).get('ci') or {})
        if ci.get('provider') != 'github-actions':
            fail(f"expected later pack to override signing ci provider, got {ci.get('provider')!r}")

        effective_promotion = load_effective_policy_domain(repo, 'promotion_policy')
        reviews = effective_promotion.get('reviews') or {}
        if reviews.get('allow_owner_when_no_distinct_reviewer') is not True:
            fail('expected policy pack to populate promotion-policy review fallback')
        groups = reviews.get('groups') or {}
        if sorted(groups) != ['maintainers', 'security']:
            fail(f'expected deep-merged promotion-policy groups, got {sorted(groups)!r}')
        required_groups = (((reviews.get('quorum') or {}).get('stage_overrides') or {}).get('active') or {}).get('required_groups')
        if required_groups != ['maintainers', 'security']:
            fail(f'expected repository-local stage override to replace required_groups, got {required_groups!r}')

        effective_namespace = load_effective_policy_domain(repo, 'namespace_policy')
        publishers = effective_namespace.get('publishers') or {}
        if sorted(publishers) != ['baseline', 'dual']:
            fail(f'expected namespace policy publishers from both packs, got {sorted(publishers)!r}')
        compatibility = effective_namespace.get('compatibility') or {}
        if compatibility.get('allow_unqualified_names') is not False:
            fail('expected baseline namespace compatibility setting to survive merge')

        effective_registry = load_effective_policy_domain(repo, 'registry_sources')
        registries = effective_registry.get('registries') or []
        if len(registries) != 1 or registries[0].get('name') != 'baseline':
            fail(f'expected registry-sources domain shape to stay compatible, got {registries!r}')

        team_resolution = load_policy_domain_resolution(repo, 'team_policy')
        team_sources = team_resolution.get('effective_sources') or []
        if [item.get('kind') for item in team_sources] != ['pack', 'local_override']:
            fail(f'unexpected team-policy source order: {team_sources!r}')
        effective_team_policy = team_resolution.get('effective') or {}
        teams = effective_team_policy.get('teams') or {}
        if sorted(teams) != ['platform-admins', 'release-operators']:
            fail(f'unexpected merged teams in team_policy: {sorted(teams)!r}')

        exception_resolution = load_policy_domain_resolution(repo, 'exception_policy')
        exception_sources = exception_resolution.get('effective_sources') or []
        if [item.get('kind') for item in exception_sources] != ['pack', 'local_override']:
            fail(f'unexpected exception-policy source order: {exception_sources!r}')
        effective_exception_policy = exception_resolution.get('effective') or {}
        exceptions = effective_exception_policy.get('exceptions') or []
        ids = sorted(item.get('id') for item in exceptions if isinstance(item, dict))
        if ids != ['pack-release-waiver', 'repo-promotion-waiver']:
            fail(f'expected merged exception-policy ids, got {ids!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_missing_pack_name_fails():
    tmpdir, repo = make_repo()
    try:
        selector = base_selector()
        selector['active_packs'] = ['baseline', 'missing-pack']
        write_json(repo / 'policy' / 'policy-packs.json', selector)
        try:
            load_effective_policy_domain(repo, 'signing')
        except PolicyPackError as exc:
            if 'missing-pack' not in str(exc):
                fail(f'expected missing pack error to mention pack name, got {exc}')
            return
        fail('expected missing active pack to raise PolicyPackError')
    finally:
        shutil.rmtree(tmpdir)


def scenario_unknown_domain_fails():
    tmpdir, repo = make_repo()
    try:
        pack = baseline_pack()
        pack['domains']['unsupported_policy'] = {'enabled': True}
        write_json(repo / 'policy' / 'packs' / 'baseline.json', pack)
        try:
            load_effective_policy_domain(repo, 'signing')
        except PolicyPackError as exc:
            if 'unsupported_policy' not in str(exc):
                fail(f'expected unsupported domain error to mention the bad key, got {exc}')
            return
        fail('expected unsupported policy domain to raise PolicyPackError')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_declared_pack_order_and_local_overrides()
    scenario_missing_pack_name_fails()
    scenario_unknown_domain_fails()
    print('OK: policy-pack loading checks passed')


if __name__ == '__main__':
    main()
