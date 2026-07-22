"""Hosted backup restore rehearsal."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import closing
from pathlib import Path
from typing import NoReturn

from infinitas_skill.hashing import sha256_file


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def load_manifest(backup_dir: Path) -> dict:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        fail(f"backup directory is missing manifest.json: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid manifest.json in {backup_dir}: {exc}")
    if not isinstance(payload, dict):
        fail(f"manifest.json must contain an object: {manifest_path}")
    return payload


def require_child(backup_dir: Path, relative_name: str, label: str) -> Path:
    path = (backup_dir / relative_name).resolve()
    if not path.is_relative_to(backup_dir.resolve()):
        fail(f"backup manifest {label} escapes its directory: {relative_name}")
    if not path.exists():
        fail(f"backup directory is missing {label}: {path}")
    return path


def verify_backup_checksums(backup_dir: Path, manifest: dict, files: list[Path]) -> None:
    if manifest.get("schema_version") != 1:
        fail("backup manifest has an unsupported schema_version")
    checksums_raw = manifest.get("checksums")
    if not isinstance(checksums_raw, dict):
        fail("backup manifest is missing checksums")
    checksums: dict[str, object] = {str(key): value for key, value in checksums_raw.items()}

    for path in files:
        expected = checksums.get(path.name)
        if not isinstance(expected, str) or len(expected) != 64:
            fail(f"backup manifest is missing SHA-256 for {path.name}")
        if sha256_file(path) != expected:
            fail(f"backup checksum mismatch for {path.name}")


def verify_bundle(bundle_path: Path) -> None:
    result = subprocess.run(
        ["git", "bundle", "verify", str(bundle_path)], text=True, capture_output=True
    )
    if result.returncode != 0:
        fail(f"git bundle verify failed for {bundle_path}\n{result.stderr}")


def clone_bundle(bundle_path: Path, output_repo: Path) -> None:
    result = subprocess.run(
        ["git", "clone", str(bundle_path), str(output_repo)], text=True, capture_output=True
    )
    if result.returncode != 0:
        fail(f"git clone failed for {bundle_path}\n{result.stderr}")


def copy_and_verify_sqlite(source_db: Path, target_db: Path) -> None:
    shutil.copy2(source_db, target_db)
    try:
        with closing(sqlite3.connect(target_db)) as connection:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        fail(f"sqlite verification failed for restored db {target_db}: {exc}")
    if integrity_rows != [("ok",)]:
        fail(f"sqlite integrity check failed for restored db {target_db}: {integrity_rows!r}")


def _validated_archive_members(archive: tarfile.TarFile, output_dir: Path) -> list[tarfile.TarInfo]:
    output_root = output_dir.resolve()
    members = archive.getmembers()
    for member in members:
        if not (member.isfile() or member.isdir()):
            fail(f"artifact archive contains unsupported member type: {member.name}")
        destination = (output_root / member.name).resolve()
        if not destination.is_relative_to(output_root):
            fail(f"artifact archive member escapes restore directory: {member.name}")
    return members


def extract_artifacts(archive_path: Path, output_dir: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = _validated_archive_members(archive, output_dir)
        archive.extractall(output_dir, members=members, filter="data")
    artifacts_dir = output_dir / "artifacts"
    if not (artifacts_dir / "ai-index.json").exists():
        fail(f"restored artifacts are missing ai-index.json: {artifacts_dir / 'ai-index.json'}")
    if not (artifacts_dir / "catalog").is_dir():
        fail(f"restored artifacts are missing catalog/: {artifacts_dir / 'catalog'}")
    return artifacts_dir


def _backup_reference(manifest: dict, section: str, field: str) -> str:
    payload = manifest.get(section)
    value = payload.get(field) if isinstance(payload, dict) else None
    return value.strip() if isinstance(value, str) else ""


def run_server_restore_rehearsal(*, backup_dir: str, output_dir: str, as_json: bool = False) -> int:
    backup = Path(backup_dir).resolve()
    if not backup.is_dir():
        fail(f"backup-dir is not a directory: {backup}")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(backup)
    repo_bundle_name = _backup_reference(manifest, "repo", "bundle")
    db_backup_name = _backup_reference(manifest, "database", "backup_file")
    archive_name = _backup_reference(manifest, "artifacts", "archive")
    if not repo_bundle_name or not db_backup_name or not archive_name:
        manifest_path = backup / "manifest.json"
        fail(f"manifest.json is missing required backup file references: {manifest_path}")

    bundle_path = require_child(backup, repo_bundle_name, "repo bundle")
    db_path = require_child(backup, db_backup_name, "database backup")
    archive_path = require_child(backup, archive_name, "artifact archive")
    verify_backup_checksums(backup, manifest, [bundle_path, db_path, archive_path])
    verify_bundle(bundle_path)

    repo_output = output / "repo"
    db_output = output / db_backup_name
    if repo_output.exists():
        shutil.rmtree(repo_output, ignore_errors=True)
    db_output.unlink(missing_ok=True)
    clone_bundle(bundle_path, repo_output)
    copy_and_verify_sqlite(db_path, db_output)
    artifacts_output = extract_artifacts(archive_path, output)
    summary = {
        "ok": True,
        "backup_dir": str(backup),
        "manifest": {
            "created_at": manifest.get("created_at"),
            "label": manifest.get("label") or "",
        },
        "paths": {
            "repo": str(repo_output),
            "database": str(db_output),
            "artifacts": str(artifacts_output),
        },
    }
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"OK: cloned repo to {repo_output}")
        print(f"OK: copied sqlite db to {db_output}")
        print(f"OK: extracted artifacts to {artifacts_output}")
    return 0


__all__ = ["extract_artifacts", "run_server_restore_rehearsal", "verify_backup_checksums"]
