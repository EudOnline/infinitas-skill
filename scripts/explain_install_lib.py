#!/usr/bin/env python3


def _dedupe_strings(values):
    seen = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _listify(value):
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _coalesce_string(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_resolve_explanation(payload):
    payload = payload if isinstance(payload, dict) else {}
    resolved = payload.get('resolved') if isinstance(payload.get('resolved'), dict) else {}
    state = payload.get('state') or 'unknown'
    registry_name = _coalesce_string(resolved.get('source_registry'))
    version = _coalesce_string(resolved.get('resolved_version'))
    reasons = []

    if state == 'resolved-private':
        selection_reason = 'selected the default-registry match because it outranks external candidates'
        reasons.append('default registry matches win before external registries')
    elif state == 'resolved-external':
        selection_reason = 'selected the external match because no default-registry candidate resolved'
        reasons.append('external registry installs require confirmation before materialization')
    elif state == 'ambiguous':
        selection_reason = 'found multiple matching skills, so no single winner was chosen'
        reasons.append('use a qualified_name to disambiguate matching candidates')
    elif state == 'incompatible':
        selection_reason = 'matched skills existed, but none satisfied the requested compatibility filters'
        reasons.append('agent compatibility blocks automatic selection when no compatible match exists')
    elif state == 'not-found':
        selection_reason = 'no discovery-index candidate matched the requested name'
        reasons.append('search again or use a qualified_name present in discovery-index.json')
    else:
        selection_reason = 'resolution did not finish with a usable candidate'
        reasons.append('inspect the resolver output and discovery catalogs before retrying')

    if version:
        version_reason = f'selected version {version} from the discovery result'
    else:
        version_reason = 'no version was selected during resolution'

    next_actions = _dedupe_strings(
        [payload.get('recommended_next_step'), 'run inspect-skill for release details' if resolved else None]
    )

    return {
        'selection_reason': selection_reason,
        'registry_used': registry_name,
        'confirmation_required': bool(payload.get('requires_confirmation')),
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }


def build_pull_plan_explanation(plan, *, requested_version=None):
    plan = plan if isinstance(plan, dict) else {}
    resolved_version = _coalesce_string(plan.get('resolved_version'), requested_version)
    reasons = ['immutable-only install policy requires released distribution artifacts']
    if plan.get('state') == 'planned':
        reasons.append('confirm mode previews the install plan without materializing files')
    selection_reason = 'prepared an immutable install plan from the selected registry entry'
    version_reason = (
        f'using resolved version {resolved_version} from the AI index'
        if resolved_version
        else 'no released version could be selected from the AI index'
    )
    next_actions = _dedupe_strings([plan.get('next_step'), 'run install-skill from the planned release artifacts'])
    return {
        'selection_reason': selection_reason,
        'registry_used': _coalesce_string(plan.get('registry_name')),
        'confirmation_required': False,
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }


def build_pull_result_explanation(plan, payload):
    plan = plan if isinstance(plan, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get('state') or plan.get('state') or 'unknown'
    resolved_version = _coalesce_string(payload.get('resolved_version'), plan.get('resolved_version'))
    reasons = ['immutable-only install policy requires released distribution artifacts']

    if state == 'installed':
        selection_reason = 'installed the selected immutable release into the target directory'
    elif state == 'failed':
        selection_reason = 'materialization failed after a release plan was selected'
        reasons.append('installation stops when release artifacts cannot be materialized safely')
    else:
        selection_reason = 'prepared a pull result from the selected immutable release'

    version_reason = (
        f'using resolved version {resolved_version} from the release plan'
        if resolved_version
        else 'no resolved version was available from the release plan'
    )
    next_actions = _dedupe_strings([payload.get('next_step'), plan.get('next_step')])
    return {
        'selection_reason': selection_reason,
        'registry_used': _coalesce_string(payload.get('registry_name'), plan.get('registry_name')),
        'confirmation_required': False,
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }


def build_install_explanation(resolve_payload, payload=None, *, requested_version=None):
    resolve_payload = resolve_payload if isinstance(resolve_payload, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    resolved = resolve_payload.get('resolved') if isinstance(resolve_payload.get('resolved'), dict) else {}
    resolved_version = _coalesce_string(
        payload.get('resolved_version'),
        requested_version,
        resolved.get('resolved_version'),
    )
    base = build_resolve_explanation(resolve_payload)
    reasons = _dedupe_strings(base.get('policy_reasons') + _listify((payload.get('explanation') or {}).get('policy_reasons')))

    if payload.get('state') == 'installed':
        selection_reason = 'installed the resolver winner using immutable registry artifacts'
    elif payload.get('state') == 'planned':
        selection_reason = 'prepared an install plan for the resolver winner without materializing files'
    elif payload.get('error_code') == 'confirmation-required':
        selection_reason = 'blocked auto-install because the selected registry requires confirmation'
    else:
        selection_reason = base.get('selection_reason')

    version_reason = (
        f'using resolved version {resolved_version} for install'
        if resolved_version
        else base.get('version_reason')
    )
    next_actions = _dedupe_strings(
        _listify((payload.get('explanation') or {}).get('next_actions'))
        + _listify(base.get('next_actions'))
        + [payload.get('next_step')]
    )
    return {
        'selection_reason': selection_reason,
        'registry_used': _coalesce_string(payload.get('source_registry'), resolved.get('source_registry'), base.get('registry_used')),
        'confirmation_required': bool(resolve_payload.get('requires_confirmation')),
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }


def build_update_explanation(info, payload):
    info = info if isinstance(info, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    installed = _coalesce_string(info.get('installed_version'), payload.get('installed_version'))
    latest = _coalesce_string(payload.get('latest_available_version'))
    if payload.get('update_available'):
        selection_reason = 'found a newer released version in the installed source registry'
    else:
        selection_reason = 'the installed version already matches the newest released version'
    version_reason = f'installed version {installed}; latest available version {latest or installed or "unknown"}'
    reasons = ['update checks stay pinned to the installed source registry']
    next_actions = _dedupe_strings([payload.get('next_step')])
    return {
        'selection_reason': selection_reason,
        'registry_used': _coalesce_string(payload.get('source_registry'), info.get('source_registry')),
        'confirmation_required': False,
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }


def build_upgrade_explanation(info, payload):
    info = info if isinstance(info, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get('state') or 'unknown'
    from_version = _coalesce_string(payload.get('from_version'), info.get('installed_version'))
    to_version = _coalesce_string(payload.get('to_version'), from_version)
    reasons = ['cross-source upgrades are blocked to preserve source provenance']

    if payload.get('error_code') == 'cross-source-upgrade-not-allowed':
        selection_reason = 'blocked the requested registry override for the installed skill'
    elif state == 'planned':
        selection_reason = 'prepared a same-registry upgrade plan without materializing files'
        reasons.append('confirm mode previews the upgrade path before switching installed files')
    elif state == 'installed':
        selection_reason = 'upgraded the installed skill in place from the same registry'
    elif state == 'up-to-date':
        selection_reason = 'no upgrade was needed because the installed version is already current'
    else:
        selection_reason = 'evaluated the upgrade request against the installed registry source'

    version_reason = f'upgrade path is {from_version or "unknown"} -> {to_version or "unknown"}'
    next_actions = _dedupe_strings([payload.get('next_step')])
    return {
        'selection_reason': selection_reason,
        'registry_used': _coalesce_string(payload.get('source_registry'), info.get('source_registry')),
        'confirmation_required': False,
        'version_reason': version_reason,
        'policy_reasons': reasons,
        'next_actions': next_actions,
    }
