#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
from urllib import error, request


class TransparencyLogError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_transparency_log_request(provenance_path, payload=None):
    provenance_path = Path(provenance_path).resolve()
    payload = payload or load_json(provenance_path)
    attestation = payload.get('attestation') or {}
    return {
        'kind': 'attestation-transparency-log-submit',
        'attestation_sha256': sha256_file(provenance_path),
        'attestation_path': provenance_path.name,
        'skill': {
            'name': (payload.get('skill') or {}).get('name'),
            'publisher': (payload.get('skill') or {}).get('publisher'),
            'qualified_name': (payload.get('skill') or {}).get('qualified_name'),
            'version': (payload.get('skill') or {}).get('version'),
        },
        'source_snapshot': payload.get('source_snapshot'),
        'attestation': {
            'format': attestation.get('format'),
            'namespace': attestation.get('namespace'),
            'signer_identity': attestation.get('signer_identity'),
            'signature_file': attestation.get('signature_file'),
        },
        'generated_at': payload.get('generated_at'),
    }


def _require_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise TransparencyLogError(f'{label} must be a non-empty string')
    return value


def _require_non_negative_int(value, label):
    if not isinstance(value, int) or value < 0:
        raise TransparencyLogError(f'{label} must be a non-negative integer')
    return value


def normalize_transparency_log_entry(response_payload, *, endpoint, request_payload):
    if not isinstance(response_payload, dict):
        raise TransparencyLogError('transparency log returned a malformed JSON object')

    expected_digest = request_payload.get('attestation_sha256')
    response_digest = _require_string(response_payload.get('attestation_sha256'), 'response.attestation_sha256')
    if response_digest != expected_digest:
        raise TransparencyLogError('transparency log proof digest does not match attestation digest')

    proof = response_payload.get('proof')
    if not isinstance(proof, dict):
        raise TransparencyLogError('transparency log response is missing proof metadata')
    proof_digest = _require_string(proof.get('body_sha256'), 'proof.body_sha256')
    if proof_digest != expected_digest:
        raise TransparencyLogError('transparency log proof body digest does not match attestation digest')

    inclusion_path = proof.get('inclusion_path')
    if not isinstance(inclusion_path, list) or any(not isinstance(item, str) or not item.strip() for item in inclusion_path):
        raise TransparencyLogError('proof.inclusion_path must be an array of non-empty strings')

    return {
        '$schema': 'schemas/transparency-log-entry.schema.json',
        'schema_version': 1,
        'kind': 'attestation-transparency-log-entry',
        'log_endpoint': endpoint,
        'entry_id': _require_string(response_payload.get('entry_id'), 'response.entry_id'),
        'log_index': _require_non_negative_int(response_payload.get('log_index'), 'response.log_index'),
        'integrated_time': _require_string(response_payload.get('integrated_time'), 'response.integrated_time'),
        'attestation_sha256': expected_digest,
        'proof': {
            'hash_algorithm': _require_string(proof.get('hash_algorithm') or 'sha256', 'proof.hash_algorithm'),
            'body_sha256': proof_digest,
            'root_hash': _require_string(proof.get('root_hash'), 'proof.root_hash'),
            'tree_size': _require_non_negative_int(proof.get('tree_size'), 'proof.tree_size'),
            'inclusion_path': inclusion_path,
        },
    }


def resolve_transparency_log_entry_path(provenance_path, descriptor=None, root=None):
    provenance_path = Path(provenance_path).resolve()
    descriptor = descriptor if isinstance(descriptor, dict) else {}
    entry_ref = descriptor.get('entry_path')
    if isinstance(entry_ref, str) and entry_ref.strip():
        ref_path = Path(entry_ref)
        if ref_path.is_absolute():
            return ref_path.resolve()
        if root is not None:
            return (Path(root).resolve() / ref_path).resolve()
        return (provenance_path.parent / ref_path).resolve()
    return provenance_path.with_name(f'{provenance_path.stem}.transparency.json')


def _relative_or_absolute(root, path):
    root = Path(root).resolve()
    path = Path(path).resolve()
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def verify_transparency_log_entry(entry_path, provenance_path):
    entry_path = Path(entry_path).resolve()
    provenance_path = Path(provenance_path).resolve()
    payload = load_json(entry_path)
    if payload.get('schema_version') != 1:
        raise TransparencyLogError('transparency log entry schema_version must be 1')
    if payload.get('kind') != 'attestation-transparency-log-entry':
        raise TransparencyLogError('transparency log entry kind must be attestation-transparency-log-entry')
    _require_string(payload.get('$schema'), 'entry.$schema')
    endpoint = _require_string(payload.get('log_endpoint'), 'entry.log_endpoint')
    return normalize_transparency_log_entry(
        payload,
        endpoint=endpoint,
        request_payload={'attestation_sha256': sha256_file(provenance_path)},
    )


def summarize_transparency_log_state(provenance_path, payload=None, root=None):
    provenance_path = Path(provenance_path).resolve()
    payload = payload or load_json(provenance_path)
    descriptor = payload.get('transparency_log') if isinstance(payload.get('transparency_log'), dict) else {}
    if not descriptor:
        default_entry_path = provenance_path.with_name(f'{provenance_path.stem}.transparency.json')
        if not default_entry_path.exists():
            return None

    mode = descriptor.get('mode', 'disabled')
    required = bool(descriptor.get('required', mode == 'required'))
    entry_path = resolve_transparency_log_entry_path(provenance_path, descriptor=descriptor, root=root)
    summary = {
        'mode': mode,
        'required': required,
        'entry_path': _relative_or_absolute(root, entry_path) if root is not None else str(entry_path),
        'published': False,
        'verified': False,
        'entry_id': None,
        'log_index': None,
        'integrated_time': None,
        'log_endpoint': None,
    }
    if not entry_path.exists():
        return summary

    entry = verify_transparency_log_entry(entry_path, provenance_path)
    summary.update(
        {
            'published': True,
            'verified': True,
            'entry_id': entry.get('entry_id'),
            'log_index': entry.get('log_index'),
            'integrated_time': entry.get('integrated_time'),
            'log_endpoint': entry.get('log_endpoint'),
        }
    )
    return summary


def submit_transparency_log_entry(endpoint, request_payload, timeout_seconds=5):
    endpoint = _require_string(endpoint, 'transparency log endpoint')
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise TransparencyLogError('transparency log timeout_seconds must be a positive integer')

    encoded = json.dumps(request_payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(
        endpoint,
        data=encoded,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode('utf-8')
            status = response.getcode()
    except error.HTTPError as exc:
        raise TransparencyLogError(f'transparency log rejected the request: HTTP {exc.code}') from exc
    except error.URLError as exc:
        reason = exc.reason if hasattr(exc, 'reason') else exc
        raise TransparencyLogError(f'could not reach transparency log endpoint {endpoint}: {reason}') from exc

    if status not in {200, 201}:
        raise TransparencyLogError(f'transparency log rejected the request: HTTP {status}')

    try:
        response_payload = json.loads(body)
    except Exception as exc:
        raise TransparencyLogError(f'transparency log returned malformed JSON: {exc}') from exc

    return normalize_transparency_log_entry(
        response_payload,
        endpoint=endpoint,
        request_payload=request_payload,
    )
