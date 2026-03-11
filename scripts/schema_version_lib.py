#!/usr/bin/env python3
SUPPORTED_SCHEMA_VERSION = 1


def validate_schema_version(payload, *, field='schema_version', default_version=SUPPORTED_SCHEMA_VERSION):
    if not isinstance(payload, dict):
        return default_version, [f'{field} validation requires an object payload']
    if field not in payload:
        return default_version, []
    value = payload.get(field)
    if not isinstance(value, int):
        return default_version, [f'{field} must be an integer']
    if value != SUPPORTED_SCHEMA_VERSION:
        return value, [f'unsupported {field} {value!r}; supported version is {SUPPORTED_SCHEMA_VERSION}']
    return value, []
