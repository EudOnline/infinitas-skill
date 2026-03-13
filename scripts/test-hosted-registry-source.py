#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from registry_source_lib import find_registry, registry_identity, resolve_registry_root, validate_registry_config


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def base_config():
    return {
        '$schema': '../schemas/registry-sources.schema.json',
        'default_registry': 'hosted',
        'registries': [
            {
                'name': 'hosted',
                'kind': 'http',
                'base_url': 'https://skills.example.com/registry',
                'enabled': True,
                'priority': 100,
                'trust': 'private',
                'auth': {
                    'mode': 'token',
                    'env': 'INFINITAS_REGISTRY_TOKEN',
                },
            }
        ],
    }


def expect_ok(cfg):
    errors = validate_registry_config(ROOT, cfg)
    if errors:
        fail(f'expected hosted registry config to pass, got errors: {errors!r}')


def expect_error(cfg, needle):
    errors = validate_registry_config(ROOT, cfg)
    if not errors:
        fail(f'expected validation error containing {needle!r}, got success')
    if not any(needle in item for item in errors):
        fail(f'expected error containing {needle!r}, got {errors!r}')


def test_valid_http_registry_config():
    cfg = base_config()
    expect_ok(cfg)


def test_http_registry_requires_base_url():
    cfg = base_config()
    cfg['registries'][0].pop('base_url')
    expect_error(cfg, "http registry 'hosted' missing non-empty base_url")


def test_http_registry_rejects_insecure_base_url_for_trusted_tiers():
    for trust in ['private', 'trusted', 'public']:
        cfg = base_config()
        cfg['registries'][0]['trust'] = trust
        cfg['registries'][0]['base_url'] = 'http://skills.example.com/registry'
        expect_error(cfg, f"registry 'hosted' with trust '{trust}' must use an https base_url")


def test_http_registry_rejects_invalid_auth_modes():
    cfg = base_config()
    cfg['registries'][0]['auth'] = {'mode': 'cookie'}
    expect_error(cfg, "registry 'hosted' auth.mode must be one of ['none', 'token']")


def test_http_registry_identity_resolves_without_local_clone():
    cfg = base_config()
    expect_ok(cfg)
    reg = find_registry(cfg, 'hosted')
    if reg is None:
        fail('expected to find hosted registry in config')

    if resolve_registry_root(ROOT, reg) is not None:
        fail('expected hosted registry root to remain None')

    identity = registry_identity(ROOT, reg)
    if identity.get('registry_kind') != 'http':
        fail(f"expected registry_kind 'http', got {identity.get('registry_kind')!r}")
    if identity.get('registry_base_url') != 'https://skills.example.com/registry':
        fail(f"expected hosted base_url in identity, got {identity.get('registry_base_url')!r}")
    if identity.get('registry_host') != 'skills.example.com':
        fail(f"expected hosted registry host, got {identity.get('registry_host')!r}")
    if identity.get('registry_root') is not None:
        fail(f"expected no local registry root, got {identity.get('registry_root')!r}")
    if identity.get('registry_commit') is not None or identity.get('registry_tag') is not None:
        fail(f'expected hosted identity to avoid git commit/tag data, got {identity!r}')


def main():
    tests = [
        test_valid_http_registry_config,
        test_http_registry_requires_base_url,
        test_http_registry_rejects_insecure_base_url_for_trusted_tiers,
        test_http_registry_rejects_invalid_auth_modes,
        test_http_registry_identity_resolves_without_local_clone,
    ]
    for test in tests:
        test()
    print('OK: hosted registry source checks passed')


if __name__ == '__main__':
    main()
