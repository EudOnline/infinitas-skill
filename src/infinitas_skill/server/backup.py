"""Backup and retention helpers for hosted server commands."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import time
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.hashing import sha256_file
from infinitas_skill.server.repo_checks import (
    fail,
    git_output,
    require_artifacts,
    require_backup_root,
    require_clean_git_repo,
    require_keep_last,
    require_sqlite_db,
)

BACKUP_DIR_RE = re.compile(r"^\d{8}T\d{6}Z(?:-[A-Za-z0-9._-]+)?$")


def sanitize_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip("-")
    return cleaned


def create_backup_dir(output_dir: str, label: str) -> tuple[Path, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = sanitize_label(label)
    dirname = f"{timestamp}-{suffix}" if suffix else timestamp
    backup_dir = root / dirname
    backup_dir.mkdir(mode=0o700)
    backup_dir.chmod(0o700)
    return backup_dir, timestamp


def create_backup_staging_dir(output_dir: str, label: str) -> tuple[Path, Path, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = sanitize_label(label)
    dirname = f"{timestamp}-{suffix}" if suffix else timestamp
    final_dir = root / dirname
    if final_dir.exists():
        fail(f"backup directory already exists: {final_dir}")
    staging_dir = root / f".{dirname}.{uuid.uuid4().hex}.incomplete"
    staging_dir.mkdir(mode=0o700)
    staging_dir.chmod(0o700)
    return staging_dir, final_dir, timestamp


@contextmanager
def backup_lock(path: Path, *, timeout_seconds: float = 120) -> Iterator[None]:
    if timeout_seconds < 0:
        fail("backup lock timeout must be zero or greater")
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with path.open("a+", encoding="utf-8") as handle:
        path.chmod(0o600)
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in {errno.EAGAIN, errno.EACCES}:
                    raise
                if time.monotonic() >= deadline:
                    fail(f"could not acquire backup lock within {timeout_seconds}s: {path}")
                time.sleep(min(0.5, max(0.01, timeout_seconds)))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_repo_bundle(repo: Path, backup_dir: Path) -> str:
    bundle_name = "repo.bundle"
    bundle_path = backup_dir / bundle_name
    result = subprocess.run(
        ["git", "-C", str(repo), "bundle", "create", str(bundle_path), "--all"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(f"failed to create repo bundle: {result.stderr}")
    bundle_path.chmod(0o600)
    return bundle_name


def copy_sqlite_db(db_path: Path, backup_dir: Path) -> str:
    db_name = db_path.name or "server.db"
    destination = backup_dir / db_name
    try:
        with closing(sqlite3.connect(db_path, timeout=30)) as source:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                integrity_rows = target.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        fail(f"failed to create sqlite backup for {db_path}: {exc}")
    if integrity_rows != [("ok",)]:
        destination.unlink(missing_ok=True)
        fail(f"sqlite backup integrity check failed for {db_path}: {integrity_rows!r}")
    destination.chmod(0o600)
    return db_name


def archive_artifacts(artifact_path: Path, backup_dir: Path) -> str:
    archive_name = "artifacts.tar.gz"
    archive_path = backup_dir / archive_name
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(artifact_path, arcname="artifacts")
    archive_path.chmod(0o600)
    return archive_name


def build_backup_checksums(backup_dir: Path, filenames: list[str]) -> dict[str, str]:
    return {filename: sha256_file(backup_dir / filename) for filename in filenames}


def classify_backup_entries(root: Path) -> tuple[list[Path], list[Path]]:
    eligible = []
    ignored = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            ignored.append(entry)
            continue
        if not BACKUP_DIR_RE.match(entry.name):
            ignored.append(entry)
            continue
        if not (entry / "manifest.json").is_file():
            ignored.append(entry)
            continue
        eligible.append(entry)
    return eligible, ignored


def _has_valid_offsite_receipt(snapshot: Path, receipt_root: Path | None) -> bool:
    receipt_path = (
        receipt_root / f"{snapshot.name}.json"
        if receipt_root is not None
        else snapshot / "offsite-receipt.json"
    )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == 1
        and payload.get("snapshot_id") == snapshot.name
        and payload.get("backup_manifest_sha256") == sha256_file(snapshot / "manifest.json")
    )


def build_prune_summary(
    root: Path,
    keep_last: int,
    *,
    require_offsite_receipt: bool = False,
    receipt_root: Path | None = None,
) -> dict:
    eligible, ignored = classify_backup_entries(root)
    protected = (
        [path for path in eligible if not _has_valid_offsite_receipt(path, receipt_root)]
        if require_offsite_receipt
        else []
    )
    eligible_desc = sorted(
        [path for path in eligible if path not in protected],
        key=lambda item: item.name,
        reverse=True,
    )
    kept = eligible_desc[:keep_last]
    deleted = eligible_desc[keep_last:]

    for path in deleted:
        shutil.rmtree(path)

    return {
        "ok": True,
        "backup_root": str(root),
        "keep_last": keep_last,
        "kept": [str(path) for path in kept],
        "deleted": [str(path) for path in deleted],
        "protected": [str(path) for path in protected],
        "ignored": [str(path) for path in ignored],
    }


def emit_backup_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup dir {summary['backup_dir']}")
    print(f"OK: repo bundle {summary['files']['repo_bundle']}")
    print(f"OK: sqlite copy {summary['files']['database']}")
    print(f"OK: artifact archive {summary['files']['artifacts']}")


def emit_prune_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup root {summary['backup_root']}")
    print(f"OK: kept {len(summary['kept'])} recognized backup directories")
    print(f"OK: deleted {len(summary['deleted'])} recognized backup directories")
    if summary["ignored"]:
        print(f"OK: ignored {len(summary['ignored'])} non-hosted entries")
    if summary["protected"]:
        print(f"OK: protected {len(summary['protected'])} backups without offsite receipts")


def run_server_backup(
    *,
    repo_path: str,
    database_url: str,
    artifact_path: str,
    output_dir: str,
    label: str = "",
    lock_path: str = "",
    lock_timeout_seconds: float = 120,
    as_json: bool = False,
) -> int:
    repo = require_clean_git_repo(repo_path)
    db_path = require_sqlite_db(database_url)
    artifacts = require_artifacts(artifact_path)
    lock = Path(lock_path).resolve() if lock_path else Path(output_dir).resolve() / ".backup.lock"
    with backup_lock(lock, timeout_seconds=lock_timeout_seconds):
        staging_dir, backup_dir, timestamp = create_backup_staging_dir(output_dir, label)
        try:
            repo_bundle_name = write_repo_bundle(repo, staging_dir)
            db_copy_name = copy_sqlite_db(db_path, staging_dir)
            artifacts_name = archive_artifacts(artifacts, staging_dir)
            manifest = _backup_manifest(
                repo=repo,
                db_path=db_path,
                database_url=database_url,
                artifacts=artifacts,
                backup_dir=staging_dir,
                timestamp=timestamp,
                label=label,
                repo_bundle_name=repo_bundle_name,
                db_copy_name=db_copy_name,
                artifacts_name=artifacts_name,
            )
            _write_backup_manifest(staging_dir, manifest)
            os.replace(staging_dir, backup_dir)
        except BaseException:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    summary = {
        "ok": True,
        "backup_dir": str(backup_dir),
        "manifest": str(backup_dir / "manifest.json"),
        "files": {
            "repo_bundle": repo_bundle_name,
            "database": db_copy_name,
            "artifacts": artifacts_name,
            "manifest": "manifest.json",
        },
    }
    emit_backup_summary(summary, as_json=as_json)
    return 0


def _backup_manifest(
    *,
    repo: Path,
    db_path: Path,
    database_url: str,
    artifacts: Path,
    backup_dir: Path,
    timestamp: str,
    label: str,
    repo_bundle_name: str,
    db_copy_name: str,
    artifacts_name: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": timestamp,
        "label": label,
        "repo": {
            "path": str(repo),
            "head": git_output(repo, "rev-parse", "HEAD"),
            "branch": git_output(repo, "branch", "--show-current"),
            "bundle": repo_bundle_name,
        },
        "database": {
            "kind": "sqlite",
            "url": database_url,
            "path": str(db_path),
            "backup_file": db_copy_name,
        },
        "artifacts": {
            "path": str(artifacts),
            "archive": artifacts_name,
        },
        "checksums": build_backup_checksums(
            backup_dir,
            [repo_bundle_name, db_copy_name, artifacts_name],
        ),
    }


def _write_backup_manifest(backup_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest_path.chmod(0o600)


def run_server_prune_backups(
    *,
    backup_root: str,
    keep_last: int,
    require_offsite_receipt: bool = False,
    receipt_root: str = "",
    as_json: bool = False,
) -> int:
    root = require_backup_root(backup_root)
    count = require_keep_last(keep_last)
    receipts = Path(receipt_root).resolve() if receipt_root else None
    summary = build_prune_summary(
        root,
        count,
        require_offsite_receipt=require_offsite_receipt,
        receipt_root=receipts,
    )
    emit_prune_summary(summary, as_json=as_json)
    return 0


__all__ = [
    "BACKUP_DIR_RE",
    "archive_artifacts",
    "build_backup_checksums",
    "build_prune_summary",
    "classify_backup_entries",
    "copy_sqlite_db",
    "create_backup_dir",
    "create_backup_staging_dir",
    "emit_backup_summary",
    "emit_prune_summary",
    "run_server_backup",
    "run_server_prune_backups",
    "sanitize_label",
    "write_repo_bundle",
]
