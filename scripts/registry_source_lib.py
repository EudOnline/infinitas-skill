#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

TRUST_TIERS = {'private', 'trusted', 'public', 'untrusted'}
PIN_MODES = {'branch', 'tag', 'commit'}
UPDATE_MODES = {'local-only', 'track', 'pinned'}
COMMIT_RE = re.compile(r'^[0-9a-fA-F]{40}$')


def registry_sources_path(root: Path) -> Path:
    return root / 'config' / 'registry-sources.json'


def load_registry_config(root: Path):
    return json.loads(registry_sources_path(root).read_text(encoding='utf-8'))


def extract_git_host(url):
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip()
    if value.startswith('git@') and ':' in value:
        return value.split('@', 1)[1].split(':', 1)[0].lower()
    parsed = urlparse(value)
    if parsed.hostname:
        return parsed.hostname.lower()
    return None


def _clean_string_list(values):
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in result:
            result.append(item)
    return result


def short_pin_value(mode, value):
    if not isinstance(value, str):
        return value
    item = value.strip()
    if mode == 'branch' and item.startswith('refs/heads/'):
        return item[len('refs/heads/'):]
    if mode == 'tag' and item.startswith('refs/tags/'):
        return item[len('refs/tags/'):]
    if mode == 'branch' and item.startswith('origin/'):
        return item.split('/', 1)[1]
    return item


def canonical_pin_ref(mode, value):
    short = short_pin_value(mode, value)
    if not isinstance(short, str) or not short:
        return None
    if mode == 'branch':
        return short if short.startswith('refs/heads/') else f'refs/heads/{short}'
    if mode == 'tag':
        return short if short.startswith('refs/tags/') else f'refs/tags/{short}'
    return None


def normalized_pin(reg):
    pin = reg.get('pin') if isinstance(reg.get('pin'), dict) else {}
    if not pin and isinstance(reg.get('branch'), str) and reg.get('branch').strip():
        pin = {'mode': 'branch', 'value': reg.get('branch').strip()}
    mode = pin.get('mode')
    value = pin.get('value')
    if isinstance(value, str):
        value = value.strip()
    return {'mode': mode, 'value': value}


def normalized_update_policy(reg):
    policy = reg.get('update_policy') if isinstance(reg.get('update_policy'), dict) else {}
    default_mode = 'local-only' if reg.get('kind') == 'local' or reg.get('local_path') else 'track'
    mode = policy.get('mode', default_mode)
    return {'mode': mode}


def normalized_allowed_hosts(reg):
    hosts = [value.lower() for value in _clean_string_list(reg.get('allowed_hosts'))]
    host = extract_git_host(reg.get('url'))
    if not hosts and host:
        hosts = [host]
    return hosts


def normalized_allowed_refs(reg):
    refs = _clean_string_list(reg.get('allowed_refs'))
    pin = normalized_pin(reg)
    default_ref = canonical_pin_ref(pin.get('mode'), pin.get('value'))
    if not refs and default_ref:
        refs = [default_ref]
    return refs


def resolve_registry_root(root: Path, reg):
    local_path = reg.get('local_path')
    if local_path:
        p = Path(local_path)
        if not p.is_absolute():
            p = (root / p).resolve()
        return p
    if reg.get('kind') == 'git':
        return (root / '.cache' / 'registries' / reg.get('name')).resolve()
    if reg.get('name') == 'self':
        return root
    return None


def _git_output(repo: Path, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def safe_git_output(repo: Path, *args):
    try:
        return _git_output(repo, *args)
    except Exception:
        return None


def git_repo_identity(repo: Path, preferred_tag=None):
    if not (repo / '.git').exists():
        return {
            'commit': None,
            'tag': None,
            'branch': None,
            'origin_url': None,
            'origin_host': None,
        }

    commit = safe_git_output(repo, 'rev-parse', 'HEAD')
    branch = safe_git_output(repo, 'branch', '--show-current') or None
    tags_output = safe_git_output(repo, 'tag', '--points-at', 'HEAD') or ''
    tags = sorted(line.strip() for line in tags_output.splitlines() if line.strip())
    origin_url = safe_git_output(repo, 'config', '--get', 'remote.origin.url') or None
    tag = None
    if preferred_tag and preferred_tag in tags:
        tag = preferred_tag
    elif tags:
        tag = tags[0]
    return {
        'commit': commit,
        'tag': tag,
        'branch': branch,
        'origin_url': origin_url,
        'origin_host': extract_git_host(origin_url),
    }


def registry_identity(root: Path, reg):
    pin = normalized_pin(reg)
    update_policy = normalized_update_policy(reg)
    reg_root = resolve_registry_root(root, reg)
    preferred_tag = short_pin_value(pin.get('mode'), pin.get('value')) if pin.get('mode') == 'tag' else None
    git_identity = git_repo_identity(reg_root, preferred_tag=preferred_tag) if reg_root and reg_root.exists() else {
        'commit': None,
        'tag': None,
        'branch': None,
        'origin_url': None,
        'origin_host': None,
    }
    return {
        'registry_name': reg.get('name'),
        'registry_kind': reg.get('kind'),
        'registry_url': reg.get('url'),
        'registry_host': extract_git_host(reg.get('url')),
        'registry_priority': reg.get('priority', 0),
        'registry_trust': reg.get('trust'),
        'registry_root': str(reg_root) if reg_root else None,
        'registry_pin_mode': pin.get('mode'),
        'registry_pin_value': pin.get('value'),
        'registry_ref': canonical_pin_ref(pin.get('mode'), pin.get('value')),
        'registry_allowed_refs': normalized_allowed_refs(reg),
        'registry_allowed_hosts': normalized_allowed_hosts(reg),
        'registry_update_mode': update_policy.get('mode'),
        'registry_commit': git_identity.get('commit'),
        'registry_tag': git_identity.get('tag'),
        'registry_branch': git_identity.get('branch'),
        'registry_origin_url': git_identity.get('origin_url'),
        'registry_origin_host': git_identity.get('origin_host'),
    }


def find_registry(cfg, name):
    for reg in cfg.get('registries', []):
        if reg.get('name') == name:
            return reg
    return None


def validate_registry_config(root: Path, cfg):
    errors = []
    registries = cfg.get('registries')
    if not isinstance(registries, list) or not registries:
        errors.append('registries must be a non-empty array')
        return errors

    seen = set()
    for reg in registries:
        if not isinstance(reg, dict):
            errors.append('each registry entry must be an object')
            continue

        name = reg.get('name')
        kind = reg.get('kind')
        trust = reg.get('trust')
        local_path = reg.get('local_path')
        branch = reg.get('branch')
        pin = normalized_pin(reg)
        update_policy = normalized_update_policy(reg)
        allowed_refs = normalized_allowed_refs(reg)
        allowed_hosts = normalized_allowed_hosts(reg)

        if not isinstance(name, str) or not name:
            errors.append('registry name must be a non-empty string')
        elif name in seen:
            errors.append(f'duplicate registry name: {name}')
        else:
            seen.add(name)

        if kind not in {'git', 'local'}:
            errors.append(f'registry {name!r} kind must be git or local')

        if trust not in TRUST_TIERS:
            errors.append(f'registry {name!r} trust must be one of {sorted(TRUST_TIERS)}')

        if 'enabled' in reg and not isinstance(reg.get('enabled'), bool):
            errors.append(f'registry {name!r} enabled must be boolean')

        if 'priority' in reg and not isinstance(reg.get('priority'), int):
            errors.append(f'registry {name!r} priority must be integer')

        if 'notes' in reg and not isinstance(reg.get('notes'), str):
            errors.append(f'registry {name!r} notes must be a string')

        if kind == 'git':
            url = reg.get('url')
            if not isinstance(url, str) or not url.strip():
                errors.append(f'git registry {name!r} missing non-empty url')
            if not isinstance(reg.get('pin'), dict):
                errors.append(f'git registry {name!r} missing pin object')
            if not isinstance(reg.get('update_policy'), dict):
                errors.append(f'git registry {name!r} missing update_policy object')

            if not isinstance(pin.get('mode'), str) or pin.get('mode') not in PIN_MODES:
                errors.append(f'registry {name!r} pin.mode must be one of {sorted(PIN_MODES)}')
            if not isinstance(pin.get('value'), str) or not pin.get('value'):
                errors.append(f'registry {name!r} pin.value must be a non-empty string')
            if pin.get('mode') == 'commit' and isinstance(pin.get('value'), str) and not COMMIT_RE.match(pin.get('value')):
                errors.append(f'registry {name!r} commit pins must use a full 40-character SHA')

            if branch is not None and (not isinstance(branch, str) or not branch.strip()):
                errors.append(f'registry {name!r} branch must be a non-empty string when set')
            if branch and pin.get('mode') == 'branch' and short_pin_value('branch', pin.get('value')) != branch.strip():
                errors.append(f'registry {name!r} branch must match pin.value for branch pins')

            if not isinstance(update_policy.get('mode'), str) or update_policy.get('mode') not in UPDATE_MODES:
                errors.append(f'registry {name!r} update_policy.mode must be one of {sorted(UPDATE_MODES)}')

            if reg.get('allowed_hosts') is not None:
                raw_hosts = reg.get('allowed_hosts')
                if not isinstance(raw_hosts, list) or not all(isinstance(item, str) and item.strip() for item in raw_hosts):
                    errors.append(f'registry {name!r} allowed_hosts must be an array of non-empty strings')
            host = extract_git_host(url)
            if host and not allowed_hosts:
                errors.append(f'registry {name!r} must declare allowed_hosts for remote git sources')
            if host and host not in allowed_hosts:
                errors.append(f'registry {name!r} url host {host!r} is not present in allowed_hosts')

            if reg.get('allowed_refs') is not None:
                raw_refs = reg.get('allowed_refs')
                if not isinstance(raw_refs, list) or not all(isinstance(item, str) and item.strip() for item in raw_refs):
                    errors.append(f'registry {name!r} allowed_refs must be an array of non-empty strings')
            desired_ref = canonical_pin_ref(pin.get('mode'), pin.get('value'))
            if pin.get('mode') in {'branch', 'tag'}:
                if not allowed_refs:
                    errors.append(f'registry {name!r} must declare allowed_refs for branch/tag pins')
                elif desired_ref not in allowed_refs:
                    errors.append(f'registry {name!r} pin ref {desired_ref!r} must be included in allowed_refs')

            if update_policy.get('mode') == 'track' and pin.get('mode') != 'branch':
                errors.append(f'registry {name!r} track policy requires a branch pin')
            if update_policy.get('mode') == 'pinned' and pin.get('mode') not in {'tag', 'commit'}:
                errors.append(f'registry {name!r} pinned policy requires a tag or commit pin')
            if update_policy.get('mode') == 'local-only' and not local_path:
                errors.append(f'registry {name!r} local-only policy requires local_path')
            if local_path is not None and (not isinstance(local_path, str) or not local_path.strip()):
                errors.append(f'registry {name!r} local_path must be a non-empty string when set')
            if local_path and update_policy.get('mode') != 'local-only':
                errors.append(f'registry {name!r} git registries with local_path must use update_policy.mode=local-only')
            if trust == 'public' and update_policy.get('mode') == 'track':
                errors.append(f'registry {name!r} public registries must use pinned or local-only updates')
            if trust == 'untrusted' and update_policy.get('mode') != 'local-only':
                errors.append(f'registry {name!r} untrusted registries may only use local-only mode')

            reg_root = resolve_registry_root(root, reg)
            if local_path and reg_root == root and update_policy.get('mode') != 'local-only':
                errors.append(f'registry {name!r} cannot sync the working repository root outside local-only mode')

        if kind == 'local':
            if not isinstance(local_path, str) or not local_path.strip():
                errors.append(f'local registry {name!r} missing non-empty local_path')
            if reg.get('update_policy') is not None and update_policy.get('mode') != 'local-only':
                errors.append(f'local registry {name!r} may only use update_policy.mode=local-only')

    if cfg.get('default_registry') not in seen:
        errors.append('default_registry must match one configured registry name')
    return errors
