#!/usr/bin/env python3
from pathlib import Path

from registry_source_lib import load_registry_config, registry_identity, registry_is_resolution_candidate, resolve_registry_root, short_pin_value

root = Path(__file__).resolve().parent.parent
cfg = load_registry_config(root)
print(f"default_registry: {cfg.get('default_registry')}")
for reg in cfg.get('registries', []):
    status = 'enabled' if reg.get('enabled', True) else 'disabled'
    identity = registry_identity(root, reg)
    resolved = resolve_registry_root(root, reg)
    pin_mode = identity.get('registry_pin_mode')
    pin_value = short_pin_value(pin_mode, identity.get('registry_pin_value')) if pin_mode else None
    commit = identity.get('registry_commit')
    tag = identity.get('registry_tag')
    commit_note = f", commit={commit[:12]}" if commit else ''
    tag_note = f", tag={tag}" if tag else ''
    federation_mode = identity.get('registry_federation_mode') or 'direct'
    allowed_publishers = ','.join(identity.get('registry_allowed_publishers') or ['-'])
    publisher_map = identity.get('registry_publisher_map') or {}
    mapping_summary = ','.join(f'{key}->{value}' for key, value in sorted(publisher_map.items())) or '-'
    immutable = 'yes' if identity.get('registry_require_immutable_artifacts') else 'no'
    resolver_candidate = 'yes' if registry_is_resolution_candidate(reg) else 'no'
    print(
        f"- {reg.get('name')}: {reg.get('kind')} {reg.get('url')} "
        f"[{status}, priority={reg.get('priority')}, trust={reg.get('trust')}, "
        f"pin={pin_mode}:{pin_value}, update={identity.get('registry_update_mode')}, "
        f"federation={federation_mode}, resolver={resolver_candidate}, immutable={immutable}] "
        f"hosts={','.join(identity.get('registry_allowed_hosts') or ['-'])} "
        f"refs={','.join(identity.get('registry_allowed_refs') or ['-'])} "
        f"publishers={allowed_publishers} "
        f"map={mapping_summary} "
        f"-> {resolved}{commit_note}{tag_note}"
    )
