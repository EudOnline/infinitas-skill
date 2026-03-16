#!/usr/bin/env python3
from copy import deepcopy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from registry_source_lib import validate_registry_config


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def base_config(registry):
    return {
        '$schema': '../schemas/registry-sources.schema.json',
        'default_registry': registry['name'],
        'registries': [registry],
    }


def federated_http_registry():
    return {
        'name': 'upstream-fed',
        'kind': 'http',
        'base_url': 'https://skills.example.com/registry',
        'enabled': True,
        'priority': 50,
        'trust': 'trusted',
        'federation': {
            'mode': 'federated',
            'allowed_publishers': ['partner'],
            'publisher_map': {
                'partner': 'partner-labs',
            },
            'require_immutable_artifacts': True,
        },
    }


def self_registry():
    return {
        'name': 'self',
        'kind': 'git',
        'url': 'https://github.com/EudOnline/infinitas-skill.git',
        'local_path': '.',
        'branch': 'main',
        'priority': 100,
        'enabled': True,
        'trust': 'private',
        'allowed_hosts': ['github.com'],
        'allowed_refs': ['refs/heads/main'],
        'pin': {
            'mode': 'branch',
            'value': 'main',
        },
        'update_policy': {
            'mode': 'local-only',
        },
    }


def tracked_git_registry():
    return {
        'name': 'tracked-upstream',
        'kind': 'git',
        'url': 'https://github.com/example/skills.git',
        'branch': 'main',
        'priority': 80,
        'enabled': True,
        'trust': 'trusted',
        'allowed_hosts': ['github.com'],
        'allowed_refs': ['refs/heads/main'],
        'pin': {
            'mode': 'branch',
            'value': 'main',
        },
        'update_policy': {
            'mode': 'track',
        },
    }


def expect_ok(cfg):
    errors = validate_registry_config(ROOT, cfg)
    if errors:
        fail(f'expected federation config to pass, got errors: {errors!r}')


def expect_error(cfg, needle):
    errors = validate_registry_config(ROOT, cfg)
    if not errors:
        fail(f'expected validation error containing {needle!r}, got success')
    if not any(needle in item for item in errors):
        fail(f'expected error containing {needle!r}, got {errors!r}')


def test_trusted_http_registry_accepts_federated_mode():
    cfg = base_config(federated_http_registry())
    expect_ok(cfg)


def test_self_registry_rejects_federation_block():
    reg = self_registry()
    reg['federation'] = {
        'mode': 'federated',
        'allowed_publishers': ['lvxiaoer'],
        'publisher_map': {
            'lvxiaoer': 'lvxiaoer',
        },
        'require_immutable_artifacts': True,
    }
    cfg = base_config(reg)
    expect_error(cfg, 'cannot federate the working repository root')


def test_untrusted_registry_rejects_federated_mode():
    reg = federated_http_registry()
    reg['trust'] = 'untrusted'
    cfg = base_config(reg)
    expect_error(cfg, "untrusted registries cannot use federation.mode='federated'")


def test_tracked_git_registry_rejects_federated_mode():
    reg = tracked_git_registry()
    reg['federation'] = {
        'mode': 'federated',
        'allowed_publishers': ['partner'],
        'publisher_map': {
            'partner': 'partner-labs',
        },
        'require_immutable_artifacts': True,
    }
    cfg = base_config(reg)
    expect_error(cfg, "federated git registries cannot use update_policy.mode='track'")


def test_publisher_map_keys_must_stay_within_allowed_publishers():
    reg = federated_http_registry()
    reg['federation'] = deepcopy(reg['federation'])
    reg['federation']['publisher_map'] = {
        'partner': 'partner-labs',
        'rogue': 'rogue-local',
    }
    cfg = base_config(reg)
    expect_error(cfg, 'publisher_map keys must be listed in federation.allowed_publishers')


def main():
    tests = [
        test_trusted_http_registry_accepts_federated_mode,
        test_self_registry_rejects_federation_block,
        test_untrusted_registry_rejects_federated_mode,
        test_tracked_git_registry_rejects_federated_mode,
        test_publisher_map_keys_must_stay_within_allowed_publishers,
    ]
    for test in tests:
        test()
    print('OK: federation trust rule checks passed')


if __name__ == '__main__':
    main()
