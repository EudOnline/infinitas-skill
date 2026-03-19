#!/usr/bin/env python3
import hashlib
import io
import json
import platform
import tarfile
import tempfile
from datetime import datetime, timezone
from gzip import GzipFile
from pathlib import Path

from attestation_lib import AttestationError, load_attestation_config, verify_attestation, verify_ci_attestation
from http_registry_lib import fetch_binary
from release_lib import ROOT


class DistributionError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data):
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _gzip_mtime(path):
    header = Path(path).read_bytes()[:8]
    if len(header) < 8 or header[:2] != b'\x1f\x8b':
        raise DistributionError(f'invalid gzip header: {path}')
    return int.from_bytes(header[4:8], 'little')


def inspect_distribution_bundle(bundle_path, *, expected_root=None):
    bundle_path = Path(bundle_path).resolve()
    file_manifest = []
    tar_mtimes = set()
    tar_uids = set()
    tar_gids = set()
    tar_unames = set()
    tar_gnames = set()

    with tarfile.open(bundle_path, mode='r:gz') as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            member_path = Path(member.name)
            if expected_root:
                if not member_path.parts or member_path.parts[0] != expected_root:
                    raise DistributionError(f'bundle member {member.name!r} is outside expected root {expected_root!r}')
                rel_path = str(Path(*member_path.parts[1:]))
            else:
                rel_path = member.name
            if not rel_path:
                raise DistributionError(f'bundle member {member.name!r} resolved to an empty relative path')
            handle = archive.extractfile(member)
            if handle is None:
                raise DistributionError(f'could not read bundle member: {member.name}')
            data = handle.read()
            file_manifest.append(
                {
                    'path': rel_path,
                    'sha256': _sha256_bytes(data),
                    'size': member.size,
                    'mode': f'{member.mode & 0o777:04o}',
                }
            )
            tar_mtimes.add(member.mtime)
            tar_uids.add(member.uid)
            tar_gids.add(member.gid)
            tar_unames.add(member.uname or '')
            tar_gnames.add(member.gname or '')

    file_manifest.sort(key=lambda item: item['path'])
    return {
        'file_manifest': file_manifest,
        'build': {
            'archive_format': 'tar.gz',
            'gzip_mtime': _gzip_mtime(bundle_path),
            'tar_mtime': min(tar_mtimes) if tar_mtimes else 0,
            'tar_uid': min(tar_uids) if tar_uids else 0,
            'tar_gid': min(tar_gids) if tar_gids else 0,
            'tar_uname': next(iter(tar_unames)) if len(tar_unames) == 1 else None,
            'tar_gname': next(iter(tar_gnames)) if len(tar_gnames) == 1 else None,
            'builder': {
                'python': platform.python_version(),
                'implementation': platform.python_implementation(),
            },
        },
    }


def _normalize_file_manifest(entries):
    if not isinstance(entries, list):
        return None
    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        normalized.append(
            {
                'path': entry.get('path'),
                'sha256': entry.get('sha256'),
                'size': entry.get('size'),
                'mode': entry.get('mode'),
            }
        )
    normalized.sort(key=lambda item: item.get('path') or '')
    return normalized


def _normalize_build(build, *, include_builder=True):
    if not isinstance(build, dict):
        return None
    normalized = {
        'archive_format': build.get('archive_format'),
        'gzip_mtime': build.get('gzip_mtime'),
        'tar_mtime': build.get('tar_mtime'),
        'tar_uid': build.get('tar_uid'),
        'tar_gid': build.get('tar_gid'),
        'tar_uname': build.get('tar_uname'),
        'tar_gname': build.get('tar_gname'),
    }
    if include_builder:
        normalized['builder'] = build.get('builder')
    return normalized


def reproducibility_summary(payload):
    if not isinstance(payload, dict):
        return {}

    summary = {}
    file_manifest = payload.get('file_manifest')
    if isinstance(file_manifest, list):
        summary['file_manifest_count'] = len(file_manifest)

    build = payload.get('build')
    if isinstance(build, dict):
        summary['build'] = build
        summary['build_archive_format'] = build.get('archive_format')

    bundle = payload.get('bundle')
    if isinstance(bundle, dict):
        if isinstance(bundle.get('path'), str) and bundle.get('path'):
            summary['bundle_path'] = bundle.get('path')
        if isinstance(bundle.get('sha256'), str) and bundle.get('sha256'):
            summary['bundle_sha256'] = bundle.get('sha256')
        if isinstance(bundle.get('file_count'), int):
            summary['bundle_file_count'] = bundle.get('file_count')

    return summary


def _normalized_publisher(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return '_legacy'


def distribution_rel_dir(skill_name, version, publisher=None):
    return Path('catalog') / 'distributions' / _normalized_publisher(publisher) / skill_name / version


def distribution_paths(root, skill_name, version, publisher=None):
    rel_dir = distribution_rel_dir(skill_name, version, publisher=publisher)
    base_dir = Path(root).resolve() / rel_dir
    return {
        'dir': base_dir,
        'rel_dir': rel_dir,
        'manifest': base_dir / 'manifest.json',
        'manifest_rel': rel_dir / 'manifest.json',
        'bundle': base_dir / 'skill.tar.gz',
        'bundle_rel': rel_dir / 'skill.tar.gz',
    }


def deterministic_bundle(skill_dir, output_path, root_dir=None):
    skill_dir = Path(skill_dir).resolve()
    output_path = Path(output_path).resolve()
    if root_dir is None:
        root_dir = skill_dir.name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = [path for path in sorted(skill_dir.rglob('*')) if path.is_file()]
    with output_path.open('wb') as raw_handle:
        with GzipFile(filename='', mode='wb', fileobj=raw_handle, mtime=0) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode='w') as archive:
                for path in files:
                    rel = path.relative_to(skill_dir)
                    arcname = str(Path(root_dir) / rel)
                    info = archive.gettarinfo(str(path), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ''
                    info.gname = ''
                    info.mtime = 0
                    with path.open('rb') as src:
                        archive.addfile(info, src)

    return {
        'format': 'tar.gz',
        'path': str(output_path),
        'sha256': sha256_file(output_path),
        'size': output_path.stat().st_size,
        'root_dir': root_dir,
        'file_count': len(files),
    }


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_distribution_manifest(payload):
    errors = []

    def require_string(mapping, key, label):
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{label} must be a non-empty string')
        return value

    if payload.get('kind') != 'skill-distribution-manifest':
        errors.append('kind must be skill-distribution-manifest')
    if payload.get('schema_version') != 1:
        errors.append('schema_version must be 1')

    skill = payload.get('skill')
    if not isinstance(skill, dict):
        errors.append('skill must be an object')
    else:
        require_string(skill, 'name', 'skill.name')
        require_string(skill, 'version', 'skill.version')

    source_snapshot = payload.get('source_snapshot')
    if not isinstance(source_snapshot, dict):
        errors.append('source_snapshot must be an object')
    else:
        for key in ['kind', 'tag', 'ref', 'commit']:
            require_string(source_snapshot, key, f'source_snapshot.{key}')
        if not isinstance(source_snapshot.get('immutable'), bool):
            errors.append('source_snapshot.immutable must be boolean')
        if not isinstance(source_snapshot.get('pushed'), bool):
            errors.append('source_snapshot.pushed must be boolean')

    bundle = payload.get('bundle')
    if not isinstance(bundle, dict):
        errors.append('bundle must be an object')
    else:
        require_string(bundle, 'path', 'bundle.path')
        if bundle.get('format') != 'tar.gz':
            errors.append('bundle.format must be tar.gz')
        require_string(bundle, 'sha256', 'bundle.sha256')
        require_string(bundle, 'root_dir', 'bundle.root_dir')
        if not isinstance(bundle.get('size'), int) or bundle.get('size') < 0:
            errors.append('bundle.size must be a non-negative integer')
        if not isinstance(bundle.get('file_count'), int) or bundle.get('file_count') < 1:
            errors.append('bundle.file_count must be a positive integer')

    registry = payload.get('registry')
    if not isinstance(registry, dict):
        errors.append('registry must be an object')
    else:
        if not isinstance(registry.get('registries_consulted'), list):
            errors.append('registry.registries_consulted must be an array')
        if not isinstance(registry.get('resolved'), list):
            errors.append('registry.resolved must be an array')

    dependencies = payload.get('dependencies')
    if not isinstance(dependencies, dict):
        errors.append('dependencies must be an object')
    else:
        if not isinstance(dependencies.get('steps'), list):
            errors.append('dependencies.steps must be an array')
        if not isinstance(dependencies.get('registries_consulted'), list):
            errors.append('dependencies.registries_consulted must be an array')

    attestation_bundle = payload.get('attestation_bundle')
    if not isinstance(attestation_bundle, dict):
        errors.append('attestation_bundle must be an object')
    else:
        for key in [
            'provenance_path',
            'provenance_sha256',
            'signature_path',
            'signature_sha256',
            'namespace',
            'allowed_signers',
        ]:
            require_string(attestation_bundle, key, f'attestation_bundle.{key}')
        required_formats = attestation_bundle.get('required_formats')
        if required_formats is not None and (not isinstance(required_formats, list) or not required_formats):
            errors.append('attestation_bundle.required_formats must be a non-empty array when present')
        elif isinstance(required_formats, list) and any(item not in {'ssh', 'ci'} for item in required_formats):
            errors.append('attestation_bundle.required_formats entries must be ssh or ci')

    return errors


def _relative_from_root(root, path):
    root = Path(root).resolve()
    path = Path(path).resolve()
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def infer_distribution_root(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    parts = manifest_path.parts
    if 'catalog' in parts:
        index = parts.index('catalog')
        if index > 0:
            return Path(*parts[:index]).resolve()
    return manifest_path.parent.resolve()


def _resolve_manifest_ref(path, ref, root=None):
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path.resolve()
    if root is not None:
        root_candidate = (Path(root).resolve() / ref_path).resolve()
        if root_candidate.exists():
            return root_candidate
    return (Path(path).resolve().parent / ref_path).resolve()


def verify_distribution_manifest(manifest_path, root=None, attestation_root=None):
    root = Path(root or ROOT).resolve()
    attestation_root = Path(attestation_root or root).resolve()
    manifest_path = Path(manifest_path).resolve()
    try:
        payload = load_json(manifest_path)
    except Exception as exc:
        raise DistributionError(f'could not parse distribution manifest {manifest_path}: {exc}') from exc

    errors = validate_distribution_manifest(payload)
    if errors:
        raise DistributionError('; '.join(errors))

    attestation_bundle = payload['attestation_bundle']
    provenance_path = _resolve_manifest_ref(manifest_path, attestation_bundle['provenance_path'], root=root)
    signature_path = _resolve_manifest_ref(manifest_path, attestation_bundle['signature_path'], root=root)
    bundle_path = _resolve_manifest_ref(manifest_path, payload['bundle']['path'], root=root)

    if not provenance_path.exists():
        raise DistributionError(f'missing attestation payload: {provenance_path}')
    if not signature_path.exists():
        raise DistributionError(f'missing attestation signature: {signature_path}')
    if not bundle_path.exists():
        raise DistributionError(f'missing distribution bundle: {bundle_path}')

    if sha256_file(provenance_path) != attestation_bundle['provenance_sha256']:
        raise DistributionError('attestation payload digest does not match manifest')
    if sha256_file(signature_path) != attestation_bundle['signature_sha256']:
        raise DistributionError('attestation signature digest does not match manifest')
    if sha256_file(bundle_path) != payload['bundle']['sha256']:
        raise DistributionError('bundle digest does not match manifest')
    if bundle_path.stat().st_size != payload['bundle']['size']:
        raise DistributionError('bundle size does not match manifest')

    try:
        attestation_result = verify_attestation(provenance_path, root=attestation_root)
    except AttestationError as exc:
        raise DistributionError(str(exc)) from exc
    required_formats = attestation_bundle.get('required_formats') or ['ssh']
    formats_verified = set(attestation_result.get('formats_verified') or [])
    if 'ci' in required_formats and 'ci' not in formats_verified:
        ci_ref = attestation_bundle.get('ci_provenance_path')
        ci_path = _resolve_manifest_ref(manifest_path, ci_ref, root=root) if ci_ref else provenance_path.with_name(f'{provenance_path.stem}.ci.json')
        if not ci_path.exists():
            raise DistributionError(f'missing CI attestation payload: {ci_path}')
        try:
            verify_ci_attestation(ci_path, root=attestation_root)
        except AttestationError as exc:
            raise DistributionError(str(exc)) from exc
        formats_verified.add('ci')
    if 'ssh' in required_formats and 'ssh' not in formats_verified:
        raise DistributionError('distribution manifest requires SSH attestation verification')
    attestation_result['formats_verified'] = sorted(formats_verified)

    provenance = load_json(provenance_path)
    signed_distribution = provenance.get('distribution') or {}
    signed_bundle = signed_distribution.get('bundle') or {}
    if not signed_bundle:
        raise DistributionError('attestation is missing distribution.bundle metadata')
    payload_file_manifest = payload.get('file_manifest')
    signed_file_manifest = signed_distribution.get('file_manifest')
    payload_build = payload.get('build')
    signed_build = signed_distribution.get('build')

    actual_bundle_metadata = None
    if payload_file_manifest is not None or signed_file_manifest is not None or payload_build is not None or signed_build is not None:
        actual_bundle_metadata = inspect_distribution_bundle(bundle_path, expected_root=signed_bundle.get('root_dir'))

    comparisons = [
        ('skill.name', payload['skill'].get('name'), provenance.get('skill', {}).get('name')),
        ('skill.version', payload['skill'].get('version'), provenance.get('skill', {}).get('version')),
        ('source_snapshot.tag', payload['source_snapshot'].get('tag'), provenance.get('source_snapshot', {}).get('tag')),
        ('source_snapshot.commit', payload['source_snapshot'].get('commit'), provenance.get('source_snapshot', {}).get('commit')),
        ('bundle.path', payload['bundle'].get('path'), signed_bundle.get('path')),
        ('bundle.sha256', payload['bundle'].get('sha256'), signed_bundle.get('sha256')),
        ('bundle.format', payload['bundle'].get('format'), signed_bundle.get('format')),
        ('bundle.root_dir', payload['bundle'].get('root_dir'), signed_bundle.get('root_dir')),
    ]
    for label, left, right in comparisons:
        if left != right:
            raise DistributionError(f'{label} does not match signed attestation payload')

    normalized_signed_file_manifest = _normalize_file_manifest(signed_file_manifest)
    if payload_file_manifest is not None:
        normalized_payload_file_manifest = _normalize_file_manifest(payload_file_manifest)
        if normalized_payload_file_manifest is None:
            raise DistributionError('distribution manifest file_manifest metadata is invalid')
        if normalized_signed_file_manifest is not None and normalized_payload_file_manifest != normalized_signed_file_manifest:
            raise DistributionError('file manifest does not match signed attestation payload')
        normalized_actual_file_manifest = _normalize_file_manifest((actual_bundle_metadata or {}).get('file_manifest'))
        if normalized_actual_file_manifest != normalized_payload_file_manifest:
            raise DistributionError('file manifest does not match distribution bundle contents')
    elif normalized_signed_file_manifest is not None:
        normalized_actual_file_manifest = _normalize_file_manifest((actual_bundle_metadata or {}).get('file_manifest'))
        if normalized_actual_file_manifest != normalized_signed_file_manifest:
            raise DistributionError('file manifest does not match signed attestation payload')

    normalized_signed_build = _normalize_build(signed_build)
    if payload_build is not None:
        normalized_payload_build = _normalize_build(payload_build)
        if normalized_payload_build is None:
            raise DistributionError('distribution manifest build metadata is invalid')
        if normalized_signed_build is not None and normalized_payload_build != normalized_signed_build:
            raise DistributionError('build metadata does not match signed attestation payload')
        normalized_actual_build = _normalize_build((actual_bundle_metadata or {}).get('build'), include_builder=False)
        if normalized_actual_build != _normalize_build(payload_build, include_builder=False):
            raise DistributionError('build metadata does not match distribution bundle contents')
    elif normalized_signed_build is not None:
        normalized_actual_build = _normalize_build((actual_bundle_metadata or {}).get('build'), include_builder=False)
        if normalized_actual_build != _normalize_build(signed_build, include_builder=False):
            raise DistributionError('build metadata does not match signed attestation payload')

    if payload.get('registry') != provenance.get('registry'):
        raise DistributionError('registry context does not match signed attestation payload')
    if payload.get('dependencies') != provenance.get('dependencies'):
        raise DistributionError('dependency context does not match signed attestation payload')

    return {
        'verified': True,
        'manifest_path': str(manifest_path),
        'bundle_path': str(bundle_path),
        'provenance_path': str(provenance_path),
        'signature_path': str(signature_path),
        'skill': payload.get('skill', {}).get('name'),
        'version': payload.get('skill', {}).get('version'),
        'source_type': 'distribution-manifest',
        'attestation': attestation_result,
        'manifest': payload,
        'provenance': provenance,
    }


def safely_extract_bundle(bundle_path, destination_root, expected_root=None):
    bundle_path = Path(bundle_path).resolve()
    destination_root = Path(destination_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle_path, mode='r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            member_path = destination_root / member.name
            resolved = member_path.resolve()
            if not resolved.is_relative_to(destination_root):
                raise DistributionError(f'unsafe bundle member path: {member.name}')
        archive.extractall(destination_root)
    if expected_root:
        source_dir = destination_root / expected_root
        if not source_dir.is_dir():
            raise DistributionError(f'expected extracted bundle root {expected_root} is missing')
        return source_dir

    dirs = [path for path in destination_root.iterdir() if path.is_dir()]
    if len(dirs) != 1:
        raise DistributionError(f'expected one extracted top-level directory, found {len(dirs)}')
    return dirs[0]


def materialize_distribution_source(source_info, root=None):
    root = Path(root or ROOT).resolve()
    info = dict(source_info or {})
    source_type = info.get('source_type') or 'working-tree'
    if source_type != 'distribution-manifest':
        path = info.get('skill_path') or info.get('path')
        if not path:
            raise DistributionError('working-tree source is missing path')
        info['materialized_path'] = path
        info['cleanup_dir'] = None
        return info

    manifest_path = info.get('distribution_manifest') or info.get('path')
    if not manifest_path:
        raise DistributionError('distribution-manifest source is missing manifest path')
    if info.get('registry_kind') == 'http':
        return _materialize_remote_distribution_source(info)
    verified = verify_distribution_manifest(manifest_path, root=root)
    payload = verified['manifest']
    expected_bundle_sha = info.get('distribution_bundle_sha256')
    manifest_bundle_sha = (payload.get('bundle') or {}).get('sha256')
    if expected_bundle_sha and manifest_bundle_sha and expected_bundle_sha != manifest_bundle_sha:
        raise DistributionError('bundle digest does not match registry metadata')
    bundle_path = verified['bundle_path']
    temp_root = Path(tempfile.mkdtemp(prefix='infinitas-distribution-'))
    materialized_path = safely_extract_bundle(
        bundle_path,
        temp_root,
        expected_root=(payload.get('bundle') or {}).get('root_dir'),
    )
    info.update(
        {
            'materialized_path': str(materialized_path),
            'cleanup_dir': str(temp_root),
            'distribution_manifest': _relative_from_root(root, manifest_path),
            'distribution_bundle': _relative_from_root(root, bundle_path),
            'distribution_bundle_sha256': payload.get('bundle', {}).get('sha256'),
            'distribution_bundle_size': payload.get('bundle', {}).get('size'),
            'distribution_bundle_root_dir': payload.get('bundle', {}).get('root_dir'),
            'distribution_bundle_file_count': payload.get('bundle', {}).get('file_count'),
            'distribution_attestation': payload.get('attestation_bundle', {}).get('provenance_path'),
            'distribution_attestation_signature': payload.get('attestation_bundle', {}).get('signature_path'),
            'distribution_attestation_sha256': payload.get('attestation_bundle', {}).get('provenance_sha256'),
            'distribution_attestation_signature_sha256': payload.get('attestation_bundle', {}).get('signature_sha256'),
            'source_snapshot_kind': payload.get('source_snapshot', {}).get('kind'),
            'source_snapshot_tag': payload.get('source_snapshot', {}).get('tag'),
            'source_snapshot_ref': payload.get('source_snapshot', {}).get('ref'),
            'source_snapshot_commit': payload.get('source_snapshot', {}).get('commit'),
            'source_stage': (payload.get('skill') or {}).get('status') or info.get('stage'),
            'registry_context': payload.get('registry'),
            'dependency_context': payload.get('dependencies'),
        }
    )
    return info


def _download_remote_ref(base_url, rel_path, temp_root, *, token_env=None):
    ref_path = Path(rel_path)
    if ref_path.is_absolute():
        raise DistributionError(f'hosted artifact path must be relative: {rel_path}')
    output = (Path(temp_root).resolve() / ref_path).resolve()
    if not output.is_relative_to(Path(temp_root).resolve()):
        raise DistributionError(f'unsafe hosted artifact path: {rel_path}')
    fetch_binary(base_url, rel_path, output, token_env=token_env)
    return output


def _materialize_remote_distribution_source(info):
    base_url = info.get('registry_base_url') or info.get('registry_url')
    if not isinstance(base_url, str) or not base_url.strip():
        raise DistributionError('hosted distribution source is missing registry_base_url')

    token_env = info.get('registry_auth_env') if info.get('registry_auth_mode') == 'token' else None
    manifest_ref = info.get('distribution_manifest') or info.get('path')
    temp_root = Path(tempfile.mkdtemp(prefix='infinitas-http-distribution-'))
    manifest_path = _download_remote_ref(base_url, manifest_ref, temp_root, token_env=token_env)
    payload = load_json(manifest_path)

    bundle_ref = (payload.get('bundle') or {}).get('path')
    attestation_bundle = payload.get('attestation_bundle') or {}
    provenance_ref = attestation_bundle.get('provenance_path')
    signature_ref = attestation_bundle.get('signature_path')
    if not bundle_ref or not provenance_ref or not signature_ref:
        raise DistributionError('hosted distribution manifest is missing bundle or attestation references')

    _download_remote_ref(base_url, bundle_ref, temp_root, token_env=token_env)
    _download_remote_ref(base_url, provenance_ref, temp_root, token_env=token_env)
    _download_remote_ref(base_url, signature_ref, temp_root, token_env=token_env)

    verified = verify_distribution_manifest(manifest_path, root=temp_root, attestation_root=ROOT)
    manifest_payload = verified['manifest']
    expected_bundle_sha = info.get('distribution_bundle_sha256')
    manifest_bundle_sha = (manifest_payload.get('bundle') or {}).get('sha256')
    if expected_bundle_sha and manifest_bundle_sha and expected_bundle_sha != manifest_bundle_sha:
        raise DistributionError('bundle digest does not match registry metadata')

    materialized_path = safely_extract_bundle(
        verified['bundle_path'],
        temp_root / '__materialized__',
        expected_root=(manifest_payload.get('bundle') or {}).get('root_dir'),
    )
    info.update(
        {
            'materialized_path': str(materialized_path),
            'cleanup_dir': str(temp_root),
            'distribution_manifest': manifest_ref,
            'distribution_bundle': bundle_ref,
            'distribution_bundle_sha256': manifest_bundle_sha,
            'distribution_bundle_size': manifest_payload.get('bundle', {}).get('size'),
            'distribution_bundle_root_dir': manifest_payload.get('bundle', {}).get('root_dir'),
            'distribution_bundle_file_count': manifest_payload.get('bundle', {}).get('file_count'),
            'distribution_attestation': provenance_ref,
            'distribution_attestation_signature': signature_ref,
            'distribution_attestation_sha256': attestation_bundle.get('provenance_sha256'),
            'distribution_attestation_signature_sha256': attestation_bundle.get('signature_sha256'),
            'source_snapshot_kind': manifest_payload.get('source_snapshot', {}).get('kind'),
            'source_snapshot_tag': manifest_payload.get('source_snapshot', {}).get('tag'),
            'source_snapshot_ref': manifest_payload.get('source_snapshot', {}).get('ref'),
            'source_snapshot_commit': manifest_payload.get('source_snapshot', {}).get('commit'),
            'source_stage': (manifest_payload.get('skill') or {}).get('status') or info.get('stage'),
            'registry_context': manifest_payload.get('registry'),
            'dependency_context': manifest_payload.get('dependencies'),
        }
    )
    return info


def manifest_index_entry(manifest_path, root):
    payload = load_json(manifest_path)
    errors = validate_distribution_manifest(payload)
    if errors:
        raise DistributionError(f'{manifest_path}: ' + '; '.join(errors))
    skill = payload.get('skill') or {}
    bundle = payload.get('bundle') or {}
    attestation_bundle = payload.get('attestation_bundle') or {}
    reproducibility = reproducibility_summary(payload)
    return {
        'name': skill.get('name'),
        'publisher': skill.get('publisher'),
        'qualified_name': skill.get('qualified_name'),
        'identity_mode': skill.get('identity_mode'),
        'version': skill.get('version'),
        'status': skill.get('status'),
        'summary': skill.get('summary'),
        'manifest_path': _relative_from_root(root, manifest_path),
        'bundle_path': bundle.get('path'),
        'bundle_sha256': bundle.get('sha256'),
        'bundle_size': bundle.get('size'),
        'bundle_file_count': bundle.get('file_count'),
        'bundle_root_dir': bundle.get('root_dir'),
        'attestation_path': attestation_bundle.get('provenance_path'),
        'attestation_signature_path': attestation_bundle.get('signature_path'),
        'attestation_sha256': attestation_bundle.get('provenance_sha256'),
        'attestation_signature_sha256': attestation_bundle.get('signature_sha256'),
        'signer_identity': attestation_bundle.get('signer_identity'),
        'namespace': attestation_bundle.get('namespace'),
        'allowed_signers': attestation_bundle.get('allowed_signers'),
        'file_manifest_count': reproducibility.get('file_manifest_count'),
        'build_archive_format': reproducibility.get('build_archive_format'),
        'source_snapshot_kind': (payload.get('source_snapshot') or {}).get('kind'),
        'source_snapshot_tag': (payload.get('source_snapshot') or {}).get('tag'),
        'source_snapshot_ref': (payload.get('source_snapshot') or {}).get('ref'),
        'source_snapshot_commit': (payload.get('source_snapshot') or {}).get('commit'),
        'registry': payload.get('registry'),
        'dependencies': payload.get('dependencies'),
        'depends_on': skill.get('depends_on', []),
        'conflicts_with': skill.get('conflicts_with', []),
        'generated_at': payload.get('generated_at'),
        'source_type': 'distribution-manifest',
    }


def load_distribution_index(root):
    root = Path(root).resolve()
    index_path = root / 'catalog' / 'distributions.json'
    if not index_path.exists():
        return []
    payload = load_json(index_path)
    skills = payload.get('skills')
    return skills if isinstance(skills, list) else []


def build_distribution_manifest_payload(provenance_path, bundle_path, root=None, attestation_root=None):
    root = Path(root or ROOT).resolve()
    attestation_root = Path(attestation_root or root).resolve()
    provenance_path = Path(provenance_path).resolve()
    bundle_path = Path(bundle_path).resolve()
    provenance = load_json(provenance_path)
    distribution = provenance.get('distribution') or {}
    signed_bundle = distribution.get('bundle') or {}
    if not signed_bundle:
        raise DistributionError('attestation payload is missing distribution.bundle metadata')
    bundle_metadata = inspect_distribution_bundle(bundle_path, expected_root=signed_bundle.get('root_dir'))

    signature_path = provenance_path.with_suffix(provenance_path.suffix + (provenance.get('attestation') or {}).get('signature_ext', '.ssig'))
    if not signature_path.exists():
        raise DistributionError(f'missing attestation signature: {signature_path}')
    attestation_cfg = load_attestation_config(attestation_root)
    required_formats = ['ssh']
    ci_path = provenance_path.with_name(f'{provenance_path.stem}.ci.json')
    if attestation_cfg.get('requires_ci_attestation'):
        required_formats.append('ci')

    skill = provenance.get('skill') or {}
    payload = {
        '$schema': 'schemas/distribution-manifest.schema.json',
        'schema_version': 1,
        'kind': 'skill-distribution-manifest',
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'skill': {
            'name': skill.get('name'),
            'publisher': skill.get('publisher'),
            'qualified_name': skill.get('qualified_name'),
            'identity_mode': skill.get('identity_mode'),
            'version': skill.get('version'),
            'status': skill.get('status'),
            'summary': skill.get('summary'),
            'author': skill.get('author'),
            'owners': skill.get('owners', []),
            'maintainers': skill.get('maintainers', []),
            'depends_on': skill.get('depends_on', []),
            'conflicts_with': skill.get('conflicts_with', []),
        },
        'source_snapshot': provenance.get('source_snapshot'),
        'bundle': {
            'path': signed_bundle.get('path'),
            'format': signed_bundle.get('format'),
            'sha256': signed_bundle.get('sha256'),
            'size': signed_bundle.get('size'),
            'root_dir': signed_bundle.get('root_dir'),
            'file_count': signed_bundle.get('file_count'),
        },
        'file_manifest': distribution.get('file_manifest') or bundle_metadata.get('file_manifest', []),
        'build': distribution.get('build') or bundle_metadata.get('build'),
        'registry': provenance.get('registry'),
        'dependencies': provenance.get('dependencies'),
        'attestation_bundle': {
            'provenance_path': _relative_from_root(root, provenance_path),
            'provenance_sha256': sha256_file(provenance_path),
            'signature_path': _relative_from_root(root, signature_path),
            'signature_sha256': sha256_file(signature_path),
            'signer_identity': (provenance.get('attestation') or {}).get('signer_identity'),
            'namespace': (provenance.get('attestation') or {}).get('namespace'),
            'allowed_signers': (provenance.get('attestation') or {}).get('allowed_signers'),
            'required_formats': required_formats,
        },
    }
    if ci_path.exists():
        payload['attestation_bundle']['ci_provenance_path'] = _relative_from_root(root, ci_path)
        payload['attestation_bundle']['ci_provenance_sha256'] = sha256_file(ci_path)
    return payload
