from __future__ import annotations

import io
import json
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from infinitas_skill.install.distribution import deterministic_bundle
from infinitas_skill.install.skill_validation import (
    SkillValidationError,
    validate_installable_skill_dir,
)
from infinitas_skill.policy.skill_identity import validate_identity_metadata

MAX_BUNDLE_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_BUNDLE_FILES = 1000
MAX_BUNDLE_MEMBERS = 2000


class ContentValidationError(Exception):
    pass


@dataclass(frozen=True)
class CanonicalSkillBundle:
    data: bytes
    declared_version: str
    metadata: dict[str, Any]


def _safe_member_path(member_name: str, *, skill_slug: str) -> PurePosixPath:
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ContentValidationError(f"unsafe bundle member path: {member_name}")
    if not member_path.parts or member_path.parts[0] != skill_slug:
        raise ContentValidationError(f"bundle root must be {skill_slug!r}")
    return member_path


def _extract_validated_bundle(raw: bytes, destination: Path, *, skill_slug: str) -> Path:
    file_count = 0
    member_count = 0
    expanded_bytes = 0
    seen_paths: set[PurePosixPath] = set()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise ContentValidationError("content bundle must be a valid tar.gz archive") from exc

    with archive:
        for member in archive:
            member_count += 1
            if member_count > MAX_BUNDLE_MEMBERS:
                raise ContentValidationError("content bundle contains too many members")
            member_path = _safe_member_path(member.name, skill_slug=skill_slug)
            if member_path in seen_paths:
                raise ContentValidationError(f"duplicate bundle member path: {member.name}")
            seen_paths.add(member_path)
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ContentValidationError(f"unsupported bundle member type: {member.name}")
            if member.isfile():
                file_count += 1
                expanded_bytes += int(member.size)
                if file_count > MAX_BUNDLE_FILES:
                    raise ContentValidationError("content bundle contains too many files")
                if expanded_bytes > MAX_EXPANDED_BYTES:
                    raise ContentValidationError("expanded content bundle exceeds size limit")
            target = destination.joinpath(*member_path.parts).resolve()
            if not target.is_relative_to(destination):
                raise ContentValidationError(f"unsafe bundle member path: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = archive.extractfile(member)
            if handle is None:
                raise ContentValidationError(f"could not read bundle member: {member.name}")
            try:
                target.write_bytes(handle.read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            except OSError as exc:
                raise ContentValidationError(
                    f"could not extract bundle member: {member.name}"
                ) from exc
    if file_count == 0:
        raise ContentValidationError("content bundle contains no files")
    return destination / skill_slug


def _validated_metadata(skill_dir: Path) -> dict[str, Any]:
    try:
        payload = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentValidationError("could not read validated skill metadata") from exc
    if not isinstance(payload, dict):
        raise ContentValidationError("validated skill metadata must be an object")
    return payload


def _declared_version(metadata: dict[str, Any]) -> str:
    version = metadata.get("version")
    if not isinstance(version, str) or not version:
        raise ContentValidationError("validated skill metadata has no version")
    return version


def validate_hosted_skill_identity(
    metadata: dict[str, Any], *, publisher: str, skill_slug: str
) -> None:
    identity, identity_errors = validate_identity_metadata(metadata)
    errors = list(identity_errors)
    expected_qualified_name = f"{publisher}/{skill_slug}"
    if identity.get("name") != skill_slug:
        errors.append(
            f"skill metadata name {identity.get('name')!r} must equal hosted slug {skill_slug!r}"
        )
    if identity.get("publisher") != publisher:
        errors.append(
            "skill metadata publisher "
            f"{identity.get('publisher')!r} must equal hosted namespace {publisher!r}"
        )
    if identity.get("qualified_name") != expected_qualified_name:
        errors.append(
            "skill metadata qualified_name "
            f"{identity.get('qualified_name')!r} must equal {expected_qualified_name!r}"
        )
    if errors:
        raise ContentValidationError("; ".join(dict.fromkeys(errors)))


def canonicalize_skill_bundle(
    raw: bytes, *, skill_slug: str, repo_root: Path
) -> CanonicalSkillBundle:
    if not raw:
        raise ContentValidationError("content bundle is empty")
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ContentValidationError("content bundle exceeds upload size limit")
    with tempfile.TemporaryDirectory(prefix="infinitas-skill-content-") as temp_dir:
        temp_root = Path(temp_dir)
        skill_dir = _extract_validated_bundle(raw, temp_root / "extracted", skill_slug=skill_slug)
        try:
            validate_installable_skill_dir(skill_dir, repo_root=repo_root)
        except SkillValidationError as exc:
            raise ContentValidationError(str(exc)) from exc
        output_path = temp_root / "canonical.tar.gz"
        deterministic_bundle(skill_dir, output_path, root_dir=skill_slug)
        metadata = _validated_metadata(skill_dir)
        return CanonicalSkillBundle(
            data=output_path.read_bytes(),
            declared_version=_declared_version(metadata),
            metadata=metadata,
        )


__all__ = [
    "ContentValidationError",
    "CanonicalSkillBundle",
    "MAX_BUNDLE_BYTES",
    "canonicalize_skill_bundle",
    "validate_hosted_skill_identity",
]
