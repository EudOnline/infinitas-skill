"""Encrypted, checksummed snapshots for OpenClaw skills and workspace data."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
MAX_ARCHIVE_MEMBERS = 100_000
MAX_EXPANDED_BYTES = 20 * 1024 * 1024 * 1024
SKILL_IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


class OpenClawSnapshotError(Exception):
    """Raised when an OpenClaw snapshot cannot be created or restored."""


@dataclass(frozen=True)
class SnapshotFile:
    area: str
    relative_path: str
    source_path: Path
    size: int
    sha256: str
    mode: int
    mtime_ns: int

    @property
    def archive_path(self) -> str:
        return f"payload/{self.area}/{self.relative_path}"

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "path": self.relative_path,
            "archive_path": self.archive_path,
            "size": self.size,
            "sha256": self.sha256,
            "mode": self.mode,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _is_ignored_path(relative: Path, *, ignore_skill_caches: bool) -> bool:
    if ignore_skill_caches and any(part in SKILL_IGNORED_NAMES for part in relative.parts):
        return True
    name = relative.name
    return name.startswith(".env") and not name.endswith(ENV_TEMPLATE_SUFFIXES)


def _collect_files(root: Path, *, area: str, ignore_skill_caches: bool) -> list[SnapshotFile]:
    if not root.is_dir():
        raise OpenClawSnapshotError(f"{area} directory does not exist: {root}")
    files: list[SnapshotFile] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if _is_ignored_path(relative, ignore_skill_caches=ignore_skill_caches):
            continue
        if path.is_symlink():
            raise OpenClawSnapshotError(f"symbolic links are not supported: {path}")
        path_stat = path.stat()
        mode = path_stat.st_mode
        if path.is_dir():
            continue
        if not stat.S_ISREG(mode):
            raise OpenClawSnapshotError(f"unsupported filesystem entry: {path}")
        files.append(
            SnapshotFile(
                area=area,
                relative_path=relative.as_posix(),
                source_path=path,
                size=path_stat.st_size,
                sha256=_sha256_file(path),
                mode=0o755 if mode & 0o111 else 0o644,
                mtime_ns=path_stat.st_mtime_ns,
            )
        )
    return files


def _snapshot_manifest(skill_dir: Path, files: list[SnapshotFile]) -> dict[str, Any]:
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise OpenClawSnapshotError(f"skill directory is missing SKILL.md: {skill_dir}")
    counts = {area: sum(1 for item in files if item.area == area) for area in ("skill", "data")}
    sizes = {
        area: sum(item.size for item in files if item.area == area) for area in ("skill", "data")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "skill": {"name": skill_name},
        "payloads": {
            area: {
                "included": counts[area] > 0,
                "file_count": counts[area],
                "size_bytes": sizes[area],
            }
            for area in ("skill", "data")
        },
        "skill_ignored_names": sorted(SKILL_IGNORED_NAMES),
        "files": [item.manifest_entry() for item in files],
    }


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes, *, mode: int = 0o600) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _add_snapshot_file(archive: tarfile.TarFile, item: SnapshotFile) -> None:
    try:
        digest = hashlib.sha256()
        copied_size = 0
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as payload:
            with item.source_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    payload.write(chunk)
                    digest.update(chunk)
                    copied_size += len(chunk)
                after = os.fstat(source.fileno())
            if (
                copied_size != item.size
                or digest.hexdigest() != item.sha256
                or after.st_mtime_ns != item.mtime_ns
            ):
                raise OpenClawSnapshotError(
                    f"snapshot source changed while it was being archived: {item.source_path}"
                )
            payload.seek(0)
            info = tarfile.TarInfo(item.archive_path)
            info.size = item.size
            info.mode = item.mode
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, payload)
    except OSError as exc:
        raise OpenClawSnapshotError(f"could not read snapshot file: {item.source_path}") from exc


def _write_plain_snapshot(path: Path, manifest: dict[str, Any], files: list[SnapshotFile]) -> None:
    with tarfile.open(path, "w:gz", compresslevel=9) as archive:
        _add_bytes(archive, "manifest.json", _manifest_bytes(manifest))
        for item in files:
            _add_snapshot_file(archive, item)
    path.chmod(0o600)


def _run_age_encrypt(source: Path, output: Path, recipients: list[str]) -> None:
    age = shutil.which("age")
    if age is None:
        raise OpenClawSnapshotError("age is required for encrypted OpenClaw data snapshots")
    command = [age, "--encrypt"]
    for recipient in recipients:
        command.extend(["--recipient", recipient])
    command.extend(["--output", str(output), str(source)])
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise OpenClawSnapshotError(f"age encryption failed: {result.stderr.strip()}")
    output.chmod(0o600)


def create_openclaw_snapshot(
    *,
    skill_dir: str | Path,
    output_path: str | Path,
    data_dir: str | Path | None = None,
    age_recipients: list[str] | None = None,
    allow_plaintext_data: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    skill = Path(skill_dir).expanduser().resolve()
    data = Path(data_dir).expanduser().resolve() if data_dir is not None else None
    output = Path(output_path).expanduser().resolve()
    recipients = [item.strip() for item in (age_recipients or []) if item.strip()]
    if recipients and output.suffix != ".age":
        raise OpenClawSnapshotError("encrypted snapshot output must end in .age")
    if not recipients and output.suffix == ".age":
        raise OpenClawSnapshotError("plaintext snapshot output must not end in .age")
    if data is not None and not recipients and not allow_plaintext_data:
        raise OpenClawSnapshotError(
            "snapshots containing workspace data require --age-recipient or --allow-plaintext-data"
        )
    if data is not None and _paths_overlap(skill, data):
        raise OpenClawSnapshotError("skill and data directories must not overlap")
    for source in (skill, data):
        if source is not None and output.is_relative_to(source):
            raise OpenClawSnapshotError(
                "snapshot output must be outside skill and data directories"
            )
    if output.exists() and not force:
        raise OpenClawSnapshotError(f"snapshot output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    skill_files = _collect_files(skill, area="skill", ignore_skill_caches=True)
    data_files = (
        _collect_files(data, area="data", ignore_skill_caches=False) if data is not None else []
    )
    files = skill_files + data_files
    manifest = _snapshot_manifest(skill, files)
    with tempfile.TemporaryDirectory(prefix="infinitas-openclaw-snapshot-") as temp_dir:
        plain = Path(temp_dir) / "snapshot.tar.gz"
        _write_plain_snapshot(plain, manifest, files)
        verification_root = Path(temp_dir) / "verification"
        verification_root.mkdir()
        verified_manifest, members = _extract_snapshot(plain, verification_root)
        _verified_payload(verified_manifest, verification_root, members)
        temporary_output = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
        try:
            if recipients:
                _run_age_encrypt(plain, temporary_output, recipients)
            else:
                shutil.copy2(plain, temporary_output)
                temporary_output.chmod(0o600)
            os.replace(temporary_output, output)
            output.chmod(0o600)
        finally:
            temporary_output.unlink(missing_ok=True)
    return {
        "ok": True,
        "snapshot": str(output),
        "encrypted": bool(recipients),
        "skill_name": manifest["skill"]["name"],
        "payloads": manifest["payloads"],
        "archive_size_bytes": output.stat().st_size,
        "archive_sha256": f"sha256:{_sha256_file(output)}",
        "manifest_digest": f"sha256:{hashlib.sha256(_manifest_bytes(manifest)).hexdigest()}",
    }


def _decrypt_snapshot(source: Path, output: Path, identities: list[str]) -> None:
    age = shutil.which("age")
    if age is None:
        raise OpenClawSnapshotError("age is required to decrypt this OpenClaw snapshot")
    if not identities:
        raise OpenClawSnapshotError("encrypted snapshots require at least one --age-identity")
    command = [age, "--decrypt"]
    for identity in identities:
        command.extend(["--identity", identity])
    command.extend(["--output", str(output), str(source)])
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise OpenClawSnapshotError(f"age decryption failed: {result.stderr.strip()}")


def _safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise OpenClawSnapshotError(f"unsafe snapshot member path: {name}")
    return path


def _extract_snapshot(archive_path: Path, output: Path) -> tuple[dict[str, Any], set[str]]:
    members_seen: set[str] = set()
    total_size = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for index, member in enumerate(archive, start=1):
            if index > MAX_ARCHIVE_MEMBERS:
                raise OpenClawSnapshotError("snapshot contains too many members")
            member_path = _safe_member_path(member.name)
            if member.name in members_seen:
                raise OpenClawSnapshotError(f"duplicate snapshot member: {member.name}")
            members_seen.add(member.name)
            if not member.isfile():
                raise OpenClawSnapshotError(f"unsupported snapshot member type: {member.name}")
            total_size += int(member.size)
            if total_size > MAX_EXPANDED_BYTES:
                raise OpenClawSnapshotError("expanded snapshot exceeds size limit")
            target = output.joinpath(*member_path.parts).resolve()
            if not target.is_relative_to(output.resolve()):
                raise OpenClawSnapshotError(
                    f"snapshot member escapes extraction root: {member.name}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = archive.extractfile(member)
            if handle is None:
                raise OpenClawSnapshotError(f"could not read snapshot member: {member.name}")
            target.write_bytes(handle.read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    manifest_path = output / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenClawSnapshotError(f"invalid snapshot manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise OpenClawSnapshotError("unsupported OpenClaw snapshot schema")
    return manifest, members_seen


def _verify_file_entry(entry: Any, extracted: Path, expected_members: set[str]) -> tuple[str, int]:
    if not isinstance(entry, dict):
        raise OpenClawSnapshotError("snapshot file entry must be an object")
    area = entry.get("area")
    relative_path = entry.get("path")
    archive_path = entry.get("archive_path")
    if area not in {"skill", "data"} or not isinstance(relative_path, str):
        raise OpenClawSnapshotError("snapshot file entry has invalid area or path")
    safe_relative = _safe_member_path(relative_path)
    if archive_path != f"payload/{area}/{safe_relative.as_posix()}":
        raise OpenClawSnapshotError("snapshot file entry has inconsistent archive_path")
    if archive_path in expected_members:
        raise OpenClawSnapshotError(f"duplicate snapshot manifest entry: {archive_path}")
    expected_members.add(archive_path)
    path = extracted.joinpath(*_safe_member_path(archive_path).parts)
    expected_size = entry.get("size")
    expected_sha256 = entry.get("sha256")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise OpenClawSnapshotError(f"snapshot file has invalid size: {archive_path}")
    if not path.is_file() or path.stat().st_size != expected_size:
        raise OpenClawSnapshotError(f"snapshot file size mismatch: {archive_path}")
    if not isinstance(expected_sha256, str) or _sha256_file(path) != expected_sha256:
        raise OpenClawSnapshotError(f"snapshot checksum mismatch: {archive_path}")
    return area, expected_size


def _verify_payload_metadata(payloads: Any, counts: dict[str, int], sizes: dict[str, int]) -> None:
    if not isinstance(payloads, dict):
        raise OpenClawSnapshotError("snapshot manifest has no payloads object")
    for area in counts:
        area_manifest = payloads.get(area)
        if not isinstance(area_manifest, dict):
            raise OpenClawSnapshotError(f"snapshot manifest has no {area} payload metadata")
        expected = {
            "included": counts[area] > 0,
            "file_count": counts[area],
            "size_bytes": sizes[area],
        }
        if any(area_manifest.get(key) != value for key, value in expected.items()):
            raise OpenClawSnapshotError(f"snapshot {area} payload metadata mismatch")


def _verified_payload(manifest: dict[str, Any], extracted: Path, members: set[str]) -> dict:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise OpenClawSnapshotError("snapshot manifest has no files array")
    expected_members = {"manifest.json"}
    counts = {"skill": 0, "data": 0}
    sizes = {"skill": 0, "data": 0}
    for entry in raw_files:
        area, size = _verify_file_entry(entry, extracted, expected_members)
        counts[area] += 1
        sizes[area] += size
    if members != expected_members:
        unexpected = sorted(members - expected_members)
        missing = sorted(expected_members - members)
        raise OpenClawSnapshotError(
            f"snapshot members do not match manifest; missing={missing}, unexpected={unexpected}"
        )
    _verify_payload_metadata(manifest.get("payloads"), counts, sizes)
    skill = extracted / "payload" / "skill"
    data = extracted / "payload" / "data"
    if not (skill / "SKILL.md").is_file():
        raise OpenClawSnapshotError("restored skill payload is missing SKILL.md")
    return {"skill": skill, "data": data, "counts": counts}


def _prepare_target(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent))
    staged = staging_root / target.name
    shutil.copytree(source, staged)
    return staged


def _validate_restore_targets(targets: list[Path], *, force: bool) -> None:
    for index, target in enumerate(targets):
        if target.exists() and not force:
            raise OpenClawSnapshotError(f"restore target already exists: {target}")
        if any(_paths_overlap(target, other) for other in targets[index + 1 :]):
            raise OpenClawSnapshotError("skill and data restore targets must not overlap")


def _stage_replacements(replacements: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    staged: list[tuple[Path, Path]] = []
    try:
        for source, target in replacements:
            staged.append((_prepare_target(source, target), target))
    except OSError as exc:
        for prepared, _target in staged:
            shutil.rmtree(prepared.parent, ignore_errors=True)
        raise OpenClawSnapshotError(f"could not stage snapshot restore: {exc}") from exc
    return staged


def _swap_staged_targets(staged: list[tuple[Path, Path]]) -> list[tuple[Path, Path | None]]:
    swapped: list[tuple[Path, Path | None]] = []
    try:
        for prepared, target in staged:
            old_candidate = target.with_name(f".{target.name}.restore-old-{uuid.uuid4().hex}")
            old_path: Path | None = None
            if target.exists():
                target.rename(old_candidate)
                old_path = old_candidate
            try:
                prepared.rename(target)
            except OSError:
                if old_path is not None and old_path.exists():
                    old_path.rename(target)
                raise
            swapped.append((target, old_path))
    except OSError as exc:
        for target, previous in reversed(swapped):
            if target.exists():
                shutil.rmtree(target)
            if previous is not None and previous.exists():
                previous.rename(target)
        raise OpenClawSnapshotError(f"could not atomically restore snapshot: {exc}") from exc
    return swapped


def _replace_targets(replacements: list[tuple[Path, Path]], *, force: bool) -> None:
    _validate_restore_targets([target for _source, target in replacements], force=force)
    staged = _stage_replacements(replacements)
    swapped: list[tuple[Path, Path | None]] = []
    try:
        swapped = _swap_staged_targets(staged)
    finally:
        for prepared, _target in staged:
            shutil.rmtree(prepared.parent, ignore_errors=True)
    for _target, previous in swapped:
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)


def restore_openclaw_snapshot(
    *,
    snapshot_path: str | Path,
    skill_target: str | Path | None = None,
    data_target: str | Path | None = None,
    age_identities: list[str] | None = None,
    verify_only: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    snapshot = Path(snapshot_path).expanduser().resolve()
    if not snapshot.is_file():
        raise OpenClawSnapshotError(f"snapshot file does not exist: {snapshot}")
    identities = [item.strip() for item in (age_identities or []) if item.strip()]
    encrypted = snapshot.suffix == ".age"
    with tempfile.TemporaryDirectory(prefix="infinitas-openclaw-restore-") as temp_dir:
        root = Path(temp_dir)
        plain = root / "snapshot.tar.gz"
        if encrypted:
            _decrypt_snapshot(snapshot, plain, identities)
        else:
            shutil.copy2(snapshot, plain)
        extracted = root / "extracted"
        extracted.mkdir()
        manifest, members = _extract_snapshot(plain, extracted)
        payload = _verified_payload(manifest, extracted, members)
        has_data = payload["counts"]["data"] > 0
        if not verify_only:
            if skill_target is None:
                raise OpenClawSnapshotError(
                    "restore requires --skill-dir unless --verify-only is used"
                )
            if has_data and data_target is None:
                raise OpenClawSnapshotError(
                    "snapshot contains data and restore requires --data-dir"
                )
            replacements = [(payload["skill"], Path(skill_target).expanduser().resolve())]
            if has_data:
                assert data_target is not None
                replacements.append((payload["data"], Path(data_target).expanduser().resolve()))
            _replace_targets(replacements, force=force)
    skill_manifest = manifest.get("skill")
    if not isinstance(skill_manifest, dict):
        raise OpenClawSnapshotError("snapshot manifest has no skill object")
    return {
        "ok": True,
        "snapshot": str(snapshot),
        "encrypted": encrypted,
        "verified": True,
        "restored": not verify_only,
        "skill_name": skill_manifest.get("name"),
        "payloads": manifest.get("payloads"),
        "archive_sha256": f"sha256:{_sha256_file(snapshot)}",
        "manifest_digest": f"sha256:{hashlib.sha256(_manifest_bytes(manifest)).hexdigest()}",
        "skill_target": str(Path(skill_target).expanduser().resolve()) if skill_target else None,
        "data_target": str(Path(data_target).expanduser().resolve()) if data_target else None,
    }


__all__ = [
    "OpenClawSnapshotError",
    "create_openclaw_snapshot",
    "restore_openclaw_snapshot",
]
