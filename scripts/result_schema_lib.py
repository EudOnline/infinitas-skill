#!/usr/bin/env python3


def _require_object(payload, prefix, errors):
    if not isinstance(payload, dict):
        errors.append(f'{prefix} must be an object')
        return False
    return True


def _require_bool(payload, key, prefix, errors):
    if not isinstance(payload.get(key), bool):
        errors.append(f'{prefix}.{key} must be a boolean')


def _require_string(payload, key, prefix, errors):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f'{prefix}.{key} must be a non-empty string')


def _require_nullable_string(payload, key, prefix, errors):
    value = payload.get(key)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        errors.append(f'{prefix}.{key} must be a non-empty string or null')


def _require_string_list(payload, key, prefix, errors):
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f'{prefix}.{key} must be an array of non-empty strings')


def _require_command_list(payload, key, prefix, errors):
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f'{prefix}.{key} must be a non-empty array')
        return
    for index, item in enumerate(value):
        if not isinstance(item, list) or not item or any(not isinstance(part, str) or not part.strip() for part in item):
            errors.append(f'{prefix}.{key}[{index}] must be an array of non-empty strings')


def _validate_pull_explanation(explanation, prefix, errors):
    if not isinstance(explanation, dict):
        errors.append(f'{prefix} must be an object')
        return
    _require_string(explanation, 'selection_reason', prefix, errors)
    _require_nullable_string(explanation, 'registry_used', prefix, errors)
    _require_bool(explanation, 'confirmation_required', prefix, errors)
    _require_string(explanation, 'version_reason', prefix, errors)
    _require_string_list(explanation, 'policy_reasons', prefix, errors)
    _require_string_list(explanation, 'next_actions', prefix, errors)


def validate_publish_result(payload):
    errors = []
    if not _require_object(payload, 'publish_result', errors):
        return errors
    _require_bool(payload, 'ok', 'publish_result', errors)
    _require_string(payload, 'state', 'publish_result', errors)
    ok = payload.get('ok')
    state = payload.get('state')

    if ok is True and state == 'planned':
        for key in ['skill', 'qualified_name', 'version', 'status', 'manifest_path', 'bundle_path', 'attestation_path', 'next_step']:
            _require_string(payload, key, 'publish_result', errors)
        _require_command_list(payload, 'commands', 'publish_result', errors)
        _require_bool(payload, 'promotion_required', 'publish_result', errors)
    elif ok is True and state == 'published':
        for key in ['skill', 'qualified_name', 'version', 'manifest_path', 'bundle_path', 'bundle_sha256', 'attestation_path', 'next_step']:
            _require_string(payload, key, 'publish_result', errors)
        _require_nullable_string(payload, 'published_at', 'publish_result', errors)
    elif ok is False and state == 'failed':
        for key in ['failed_at_step', 'error_code', 'message', 'suggested_action']:
            _require_string(payload, key, 'publish_result', errors)
        for key in ['skill', 'qualified_name', 'version']:
            if key in payload:
                _require_string(payload, key, 'publish_result', errors)
    else:
        errors.append('publish_result state/ok combination is not supported')
    return errors


def validate_pull_result(payload):
    errors = []
    if not _require_object(payload, 'pull_result', errors):
        return errors
    _require_bool(payload, 'ok', 'pull_result', errors)
    _require_string(payload, 'state', 'pull_result', errors)
    ok = payload.get('ok')
    state = payload.get('state')

    if ok is True and state == 'planned':
        for key in [
            'qualified_name',
            'resolved_version',
            'registry_name',
            'ai_index_path',
            'target_dir',
            'manifest_path',
            'bundle_path',
            'bundle_sha256',
            'attestation_path',
            'registry_kind',
            'install_name',
            'next_step',
        ]:
            _require_string(payload, key, 'pull_result', errors)
        _require_nullable_string(payload, 'requested_version', 'pull_result', errors)
        _require_nullable_string(payload, 'registry_root', 'pull_result', errors)
        _require_string_list(payload, 'install_command', 'pull_result', errors)
        _validate_pull_explanation(payload.get('explanation'), 'pull_result.explanation', errors)
    elif ok is True and state == 'installed':
        for key in [
            'qualified_name',
            'resolved_version',
            'target_dir',
            'lockfile_path',
            'installed_files_manifest',
            'next_step',
        ]:
            _require_string(payload, key, 'pull_result', errors)
        _require_nullable_string(payload, 'requested_version', 'pull_result', errors)
        _validate_pull_explanation(payload.get('explanation'), 'pull_result.explanation', errors)
    elif ok is False and state == 'failed':
        for key in ['failed_at_step', 'error_code', 'message', 'suggested_action']:
            _require_string(payload, key, 'pull_result', errors)
        for key in ['qualified_name', 'resolved_version', 'target_dir']:
            if key in payload:
                _require_string(payload, key, 'pull_result', errors)
        if 'requested_version' in payload:
            _require_nullable_string(payload, 'requested_version', 'pull_result', errors)
        if 'explanation' in payload:
            _validate_pull_explanation(payload.get('explanation'), 'pull_result.explanation', errors)
    else:
        errors.append('pull_result state/ok combination is not supported')
    return errors
