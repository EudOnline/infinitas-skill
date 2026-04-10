from __future__ import annotations

import gzip
import io
import json
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from infinitas_skill.install.distribution import (
    DistributionError,
    build_distribution_manifest_payload,
    verify_distribution_manifest,
)
from infinitas_skill.release.attestation import (
    load_attestation_config,
    resolve_attestation_key,
)
from infinitas_skill.release.policy_state import resolve_releaser_identity
from infinitas_skill.release.signing_bootstrap import (
    parse_allowed_signers,
    public_key_from_key_path,
    signer_identities_for_key,
)
from server.artifact_ops import sha256_bytes
from server.modules.authoring.service import load_metadata
from infinitas_skill.release.service import collect_release_state
from infinitas_skill.release.release_resolution import resolve_skill
from server.modules.release import service
from server.modules.release.models import Artifact, Release
from server.modules.release.storage import ArtifactStorage, build_artifact_storage


def _canonical_json_bytes(payload: dict) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_value(repo_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _content_ref_commit(content_ref: str, fallback: str) -> str:
    ref = str(content_ref or "")
    if "#" in ref:
        candidate = ref.rsplit("#", 1)[-1].strip()
        if candidate:
            return candidate
    return fallback


def _bundle_bytes(*, skill_slug: str, content_ref: str, metadata: dict) -> tuple[bytes, int]:
    buffer = io.BytesIO()
    file_count = 0
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.PAX_FORMAT) as archive:
            entries = {
                f"{skill_slug}/snapshot/content-ref.txt": (
                    content_ref.rstrip("\n") + "\n"
                ).encode("utf-8"),
                f"{skill_slug}/snapshot/metadata.json": _canonical_json_bytes(metadata),
            }
            file_count = len(entries)
            for path, raw in entries.items():
                info = tarfile.TarInfo(name=path)
                info.size = len(raw)
                info.mtime = 0
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue(), file_count


def _resolve_signer_identity(
    *,
    repo_root: Path,
    allowed_signers_path: Path,
    signing_key: str,
) -> str:
    entries = parse_allowed_signers(allowed_signers_path)
    if not entries:
        raise RuntimeError(
            f"{allowed_signers_path.relative_to(repo_root)} has no signer entries; "
            "materialized releases require trusted SSH signers"
        )
    public_key = public_key_from_key_path(signing_key)
    identities = signer_identities_for_key(entries, public_key)
    if not identities:
        raise RuntimeError(
            f"configured signing key {signing_key} is not trusted by "
            f"{allowed_signers_path.relative_to(repo_root)}"
        )
    return identities[0]


def _sign_provenance(
    *,
    provenance_bytes: bytes,
    provenance_filename: str,
    signing_key: str,
    namespace: str,
    signature_ext: str,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="infinitas-release-provenance-") as temp_dir:
        provenance_path = Path(temp_dir) / provenance_filename
        provenance_path.write_bytes(provenance_bytes)
        signature_path = Path(f"{provenance_path}{signature_ext}")
        signature_path.unlink(missing_ok=True)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(Path(signing_key).expanduser()),
                "-n",
                namespace,
                str(provenance_path),
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "ssh-keygen failed"
            raise RuntimeError(f"could not sign release provenance: {message}")
        generated_signature = Path(f"{provenance_path}.sig")
        if generated_signature.exists():
            generated_signature.replace(signature_path)
        if not signature_path.exists():
            raise RuntimeError("ssh-keygen did not produce a provenance signature file")
        return signature_path.read_bytes()


def _build_provenance_payload(
    *,
    snapshot,
    release: Release,
    repo_root: Path,
    bundle_public_path: str,
    manifest_public_path: str,
    bundle_sha256: str,
    bundle_size: int,
    bundle_root_dir: str,
    bundle_file_count: int,
    signature_filename: str,
    attestation_cfg: dict,
    signer_identity: str,
) -> dict:
    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    qualified_name = f"{publisher}/{skill_slug}"
    release_marker = f"registry/{qualified_name}/v{version}"
    release_ref = f"refs/registry-releases/{qualified_name}/{version}"
    repo_url = _git_value(repo_root, "config", "--get", "remote.origin.url")
    branch = _git_value(repo_root, "branch", "--show-current")
    upstream = _git_value(repo_root, "rev-parse", "--abbrev-ref", "@{upstream}")
    head_commit = _git_value(repo_root, "rev-parse", "HEAD")
    source_commit = _content_ref_commit(
        snapshot.draft.content_ref,
        snapshot.skill_version.content_digest,
    )
    source_snapshot = {
        "kind": "content-ref",
        "tag": release_marker,
        "ref": snapshot.draft.content_ref,
        "commit": source_commit,
        "remote": repo_url,
        "upstream": upstream,
        "immutable": True,
        "pushed": False,
    }
    registry_payload = {
        "default_registry": "hosted",
        "registries_consulted": ["hosted"],
        "resolved": [
            {
                "registry_name": "hosted",
                "registry_kind": "http",
                "registry_url": None,
                "registry_host": None,
                "registry_priority": 100,
                "registry_trust": "private",
                "registry_root": str(repo_root),
                "registry_pin_mode": "server-generated",
                "registry_pin_value": release_marker,
                "registry_ref": release_ref,
                "registry_allowed_refs": [],
                "registry_allowed_hosts": [],
                "registry_update_mode": "server-managed",
                "registry_commit": head_commit or source_commit,
                "registry_tag": release_marker,
                "registry_branch": branch,
                "registry_origin_url": repo_url,
                "registry_origin_host": None,
            }
        ],
    }
    dependency_step = {
        "order": 1,
        "name": skill_slug,
        "publisher": publisher,
        "qualified_name": qualified_name,
        "identity_mode": "qualified",
        "version": version,
        "registry": "hosted",
        "stage": "sealed",
        "path": snapshot.draft.content_ref,
        "skill_path": snapshot.draft.content_ref,
        "relative_path": None,
        "source_type": "content-ref",
        "distribution_manifest": manifest_public_path,
        "distribution_bundle": bundle_public_path,
        "distribution_bundle_sha256": bundle_sha256,
        "distribution_attestation": None,
        "distribution_attestation_signature": None,
        "action": "install",
        "needs_apply": True,
        "requested_by": [],
        "depends_on": [],
        "conflicts_with": [],
        "root": True,
        "source_commit": source_commit,
        "source_ref": snapshot.draft.content_ref,
        "source_tag": release_marker,
        "source_snapshot_kind": source_snapshot["kind"],
        "source_snapshot_tag": source_snapshot["tag"],
        "source_snapshot_ref": source_snapshot["ref"],
        "source_snapshot_commit": source_snapshot["commit"],
    }
    releaser_identity = resolve_releaser_identity(repo_root)
    return {
        "$schema": "schemas/provenance.schema.json",
        "schema_version": 1,
        "kind": "skill-release-attestation",
        "generated_at": _utc_now_iso(),
        "skill": {
            "name": skill_slug,
            "publisher": publisher,
            "qualified_name": qualified_name,
            "identity_mode": "qualified",
            "version": version,
            "status": "active",
            "summary": snapshot.skill.summary,
            "path": f"server-generated/{publisher}/{skill_slug}",
            "author": publisher,
            "owners": [publisher],
            "maintainers": [publisher],
            "depends_on": [],
            "conflicts_with": [],
        },
        "git": {
            "repo_url": repo_url,
            "branch": branch,
            "upstream": upstream,
            "commit": source_commit,
            "head_commit": head_commit,
            "expected_tag": release_marker,
            "release_ref": release_ref,
            "remote": None,
            "remote_tag_object": None,
            "remote_tag_commit": None,
            "signed_tag_verified": True,
            "tag_signer": signer_identity,
        },
        "source_snapshot": source_snapshot,
        "registry": registry_payload,
        "dependencies": {
            "mode": "install",
            "root": {
                "name": skill_slug,
                "publisher": publisher,
                "qualified_name": qualified_name,
                "version": version,
                "registry": "hosted",
                "stage": "sealed",
                "path": snapshot.draft.content_ref,
                "source_type": "content-ref",
                "distribution_manifest": manifest_public_path,
                "source_snapshot_tag": source_snapshot["tag"],
                "source_snapshot_commit": source_snapshot["commit"],
            },
            "steps": [dependency_step],
            "registries_consulted": ["hosted"],
        },
        "review": {
            "reviewers": [],
            "effective_review_state": "not_applicable",
            "required_approvals": 0,
            "required_groups": [],
            "covered_groups": [],
            "missing_groups": [],
            "approval_count": 0,
            "blocking_rejection_count": 0,
            "quorum_met": True,
            "review_gate_pass": True,
            "latest_decisions": [],
            "ignored_decisions": [],
            "configured_groups": {},
        },
        "release": {
            "releaser_identity": releaser_identity,
            "release_mode": "local-tag",
            "transfer_required": False,
            "transfer_authorized": True,
            "authorized_signers": [signer_identity],
            "authorized_releasers": [releaser_identity] if releaser_identity else [],
            "transfer_matches": [],
            "competing_claims": [],
        },
        "attestation": {
            "format": attestation_cfg["format"],
            "namespace": attestation_cfg["namespace"],
            "allowed_signers": attestation_cfg["allowed_signers_rel"],
            "signature_file": signature_filename,
            "signature_ext": attestation_cfg["signature_ext"],
            "signer_identity": signer_identity,
            "policy_mode": attestation_cfg["policy_mode"],
            "require_verified_attestation_for_release_output": attestation_cfg[
                "require_release_output"
            ],
            "require_verified_attestation_for_distribution": attestation_cfg[
                "require_distribution"
            ],
        },
        "distribution": {
            "manifest_path": manifest_public_path,
            "bundle": {
                "path": bundle_public_path,
                "format": "tar.gz",
                "sha256": bundle_sha256,
                "size": bundle_size,
                "root_dir": bundle_root_dir,
                "file_count": bundle_file_count,
            },
        },
        "release_snapshot": {
            "release_id": release.id,
            "skill_version_id": snapshot.skill_version.id,
            "draft_id": snapshot.draft.id,
        },
    }


def materialize_release(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    repo_root: Path,
    storage_backend: ArtifactStorage | None = None,
) -> tuple[Release, list[Artifact]]:
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)
    repo_root = Path(repo_root).resolve()
    if _existing_materialization_is_current(
        snapshot=snapshot,
        release=release,
        existing_artifacts=existing_artifacts,
        artifact_root=artifact_root,
        repo_root=repo_root,
    ):
        return release, existing_artifacts

    metadata = load_metadata(snapshot.draft.metadata_json)
    publisher = snapshot.namespace.slug
    version = snapshot.skill_version.version
    skill_slug = snapshot.skill.slug
    provenance_basename = f"{publisher}--{skill_slug}-{version}.json"

    bundle_public_path = f"skills/{publisher}/{skill_slug}/{version}/skill.tar.gz"
    manifest_public_path = f"skills/{publisher}/{skill_slug}/{version}/manifest.json"
    provenance_public_path = f"provenance/{provenance_basename}"
    signature_public_path = f"provenance/{provenance_basename}.ssig"

    storage = storage_backend or build_artifact_storage(artifact_root)
    bundle_root_dir = skill_slug
    bundle_bytes, bundle_file_count = _bundle_bytes(
        skill_slug=skill_slug,
        content_ref=snapshot.draft.content_ref,
        metadata=metadata,
    )
    stored_bundle = storage.put_bytes(bundle_bytes, public_path=bundle_public_path)
    attestation_cfg = load_attestation_config(repo_root)
    signing_key = resolve_attestation_key(root=repo_root, config=attestation_cfg)
    signer_identity = _resolve_signer_identity(
        repo_root=repo_root,
        allowed_signers_path=attestation_cfg["allowed_signers_path"],
        signing_key=signing_key,
    )
    provenance_payload = _build_provenance_payload(
        snapshot=snapshot,
        release=release,
        repo_root=repo_root,
        bundle_public_path=bundle_public_path,
        manifest_public_path=manifest_public_path,
        bundle_sha256=stored_bundle.sha256,
        bundle_size=stored_bundle.size_bytes,
        bundle_root_dir=bundle_root_dir,
        bundle_file_count=bundle_file_count,
        signature_filename=Path(signature_public_path).name,
        attestation_cfg=attestation_cfg,
        signer_identity=signer_identity,
    )
    provenance_bytes = _canonical_json_bytes(provenance_payload)
    signature_bytes = _sign_provenance(
        provenance_bytes=provenance_bytes,
        provenance_filename=provenance_basename,
        signing_key=signing_key,
        namespace=attestation_cfg["namespace"],
        signature_ext=attestation_cfg["signature_ext"],
    )
    stored_provenance = storage.put_bytes(provenance_bytes, public_path=provenance_public_path)
    stored_signature = storage.put_bytes(signature_bytes, public_path=signature_public_path)
    manifest_payload = build_distribution_manifest_payload(
        artifact_root / provenance_public_path,
        artifact_root / bundle_public_path,
        root=artifact_root,
        attestation_root=repo_root,
    )
    manifest_bytes = _canonical_json_bytes(manifest_payload)
    stored_manifest = storage.put_bytes(manifest_bytes, public_path=manifest_public_path)

    bundle_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="bundle",
        storage_uri=stored_bundle.storage_uri,
        sha256=stored_bundle.sha256,
        size_bytes=stored_bundle.size_bytes,
    )
    manifest_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="manifest",
        storage_uri=stored_manifest.storage_uri,
        sha256=stored_manifest.sha256,
        size_bytes=stored_manifest.size_bytes,
    )
    provenance_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="provenance",
        storage_uri=stored_provenance.storage_uri,
        sha256=stored_provenance.sha256,
        size_bytes=stored_provenance.size_bytes,
    )
    signature_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="signature",
        storage_uri=stored_signature.storage_uri,
        sha256=stored_signature.sha256,
        size_bytes=stored_signature.size_bytes,
    )
    try:
        skill_dir = resolve_skill(repo_root, skill_slug)
        release_state = collect_release_state(skill_dir, mode="stable-release", root=repo_root)
        platform_compatibility = release_state.get("release", {}).get("platform_compatibility", {})
    except Exception:
        platform_compatibility = {
            "canonical_runtime_platform": "openclaw",
            "canonical_runtime": {},
            "blocking_platforms": [],
        }
    release.platform_compatibility_json = json.dumps(platform_compatibility, ensure_ascii=False)
    db.add(release)
    db.flush()

    service.mark_release_ready(
        db,
        release=release,
        manifest_artifact_id=manifest_artifact.id,
        bundle_artifact_id=bundle_artifact.id,
        signature_artifact_id=signature_artifact.id,
        provenance_artifact_id=provenance_artifact.id,
    )
    return release, service.get_artifacts_for_release(db, release.id)


def release_requires_materialization(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)
    return not _existing_materialization_is_current(
        snapshot=snapshot,
        release=release,
        existing_artifacts=existing_artifacts,
        artifact_root=artifact_root,
        repo_root=Path(repo_root).resolve(),
    )


def _existing_materialization_is_current(
    *,
    snapshot,
    release: Release,
    existing_artifacts: list[Artifact],
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    if (
        release.state != "ready"
        or release.manifest_artifact_id is None
        or release.bundle_artifact_id is None
        or release.signature_artifact_id is None
        or release.provenance_artifact_id is None
        or len(existing_artifacts) < 4
    ):
        return False

    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    manifest_path = (
        Path(artifact_root).resolve()
        / "skills"
        / publisher
        / skill_slug
        / version
        / "manifest.json"
    )
    try:
        verified = verify_distribution_manifest(
            manifest_path,
            root=artifact_root,
            attestation_root=repo_root,
        )
    except DistributionError:
        return False
    if not bool(verified.get("verified")):
        return False
    return _artifact_rows_match_materialized_files(
        release=release,
        existing_artifacts=existing_artifacts,
        artifact_root=artifact_root,
        publisher=publisher,
        skill_slug=skill_slug,
        version=version,
    )


def _artifact_rows_match_materialized_files(
    *,
    release: Release,
    existing_artifacts: list[Artifact],
    artifact_root: Path,
    publisher: str,
    skill_slug: str,
    version: str,
) -> bool:
    paths_by_kind = {
        "bundle": (
            Path(artifact_root)
            / "skills"
            / publisher
            / skill_slug
            / version
            / "skill.tar.gz"
        ),
        "manifest": (
            Path(artifact_root)
            / "skills"
            / publisher
            / skill_slug
            / version
            / "manifest.json"
        ),
        "provenance": (
            Path(artifact_root)
            / "provenance"
            / f"{publisher}--{skill_slug}-{version}.json"
        ),
        "signature": Path(artifact_root)
        / "provenance"
        / f"{publisher}--{skill_slug}-{version}.json.ssig",
    }
    release_artifact_ids = {
        "bundle": release.bundle_artifact_id,
        "manifest": release.manifest_artifact_id,
        "provenance": release.provenance_artifact_id,
        "signature": release.signature_artifact_id,
    }
    artifacts_by_id = {int(item.id): item for item in existing_artifacts}

    for kind, path in paths_by_kind.items():
        artifact_id = release_artifact_ids.get(kind)
        if artifact_id is None:
            return False
        artifact = artifacts_by_id.get(int(artifact_id))
        if artifact is None or str(artifact.kind) != kind:
            return False
        if not path.is_file():
            return False
        raw = path.read_bytes()
        if sha256_bytes(raw) != artifact.sha256:
            return False
        if len(raw) != int(artifact.size_bytes or 0):
            return False
    return True
