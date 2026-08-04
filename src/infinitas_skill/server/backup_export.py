"""Encrypted offsite export and recovery checks for hosted backups."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import tarfile
import tempfile
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from infinitas_skill.hashing import sha256_file
from infinitas_skill.server.backup import classify_backup_entries
from infinitas_skill.server.backup_webdav import (
    WebDAVClient,
    fail,
)
from infinitas_skill.server.backup_webdav import (
    client_from_environment as _client_from_environment,
)
from infinitas_skill.server.backup_webdav import (
    remote_path as _remote_path,
)
from infinitas_skill.server.restore import (
    load_manifest,
    require_child,
    run_server_restore_rehearsal,
    verify_backup_checksums,
    verify_bundle,
)

RECEIPT_NAME = "offsite-receipt.json"
RECEIPT_SCHEMA_VERSION = 1


def _manifest_reference(manifest: dict[str, Any], section: str, field: str) -> str:
    section_value = manifest.get(section)
    value = section_value.get(field) if isinstance(section_value, dict) else None
    return value.strip() if isinstance(value, str) else ""


def validate_backup_snapshot(backup_dir: Path) -> tuple[dict[str, Any], list[Path]]:
    manifest_path = backup_dir / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        fail(f"backup manifest must be a regular file: {manifest_path}")
    manifest = load_manifest(backup_dir)
    names = [
        _manifest_reference(manifest, "repo", "bundle"),
        _manifest_reference(manifest, "database", "backup_file"),
        _manifest_reference(manifest, "artifacts", "archive"),
    ]
    if any(not name for name in names):
        fail(f"backup manifest is missing required file references: {backup_dir / 'manifest.json'}")
    files = [require_child(backup_dir, name, "backup file") for name in names]
    if any(path.is_symlink() or not path.is_file() for path in files):
        fail(f"backup contains a non-regular referenced file: {backup_dir}")
    verify_backup_checksums(backup_dir, manifest, files)
    verify_bundle(files[0])
    try:
        with closing(sqlite3.connect(files[1])) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        fail(f"sqlite backup verification failed for {files[1]}: {exc}")
    if integrity != [("ok",)]:
        fail(f"sqlite backup integrity check failed for {files[1]}: {integrity!r}")
    return manifest, [manifest_path, *files]


def create_snapshot_archive(backup_dir: Path, files: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_path, "w:gz") as archive:
        for path in files:
            archive.add(path, arcname=path.name, recursive=False)
    output_path.chmod(0o600)


def run_age_encrypt(source: Path, output: Path, recipient: str) -> None:
    if not recipient.strip():
        fail("age recipient is required")
    result = subprocess.run(
        ["age", "--recipient", recipient.strip(), "--output", str(output), str(source)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        fail(f"age encryption failed: {result.stderr.strip()}")
    output.chmod(0o600)


def run_age_decrypt(source: Path, output: Path, identity: Path) -> None:
    if not identity.is_file():
        fail(f"age identity is not a file: {identity}")
    result = subprocess.run(
        ["age", "--decrypt", "--identity", str(identity), "--output", str(output), str(source)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        fail(f"age decryption failed: {result.stderr.strip()}")
    output.chmod(0o600)


def _receipt_paths(backup_dir: Path, remote_prefix: str) -> tuple[str, str]:
    try:
        created = datetime.strptime(backup_dir.name[:16], "%Y%m%dT%H%M%SZ")
    except ValueError:
        fail(f"backup directory has an invalid timestamp: {backup_dir.name}")
    stem = f"{backup_dir.name}.tar.gz.age"
    archive = _remote_path(f"{remote_prefix.strip('/')}/v1/{created:%Y}/{created:%m}/{stem}")
    return archive, f"{archive}.receipt.json"


def _build_receipt(
    backup_dir: Path, manifest_sha: str, encrypted_path: Path, remote_archive: str
) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "snapshot_id": backup_dir.name,
        "backup_manifest_sha256": manifest_sha,
        "encrypted_sha256": sha256_file(encrypted_path),
        "encrypted_size_bytes": encrypted_path.stat().st_size,
        "remote_archive_path": remote_archive,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _receipt_matches(
    receipt: dict[str, Any],
    snapshot_id: str,
    manifest_sha: str,
    *,
    remote_archive: str | None = None,
) -> bool:
    return (
        receipt.get("schema_version") == RECEIPT_SCHEMA_VERSION
        and receipt.get("snapshot_id") == snapshot_id
        and receipt.get("backup_manifest_sha256") == manifest_sha
        and isinstance(receipt.get("encrypted_sha256"), str)
        and len(receipt["encrypted_sha256"]) == 64
        and isinstance(receipt.get("encrypted_size_bytes"), int)
        and receipt["encrypted_size_bytes"] > 0
        and isinstance(receipt.get("remote_archive_path"), str)
        and (remote_archive is None or receipt["remote_archive_path"] == remote_archive)
        and isinstance(receipt.get("completed_at"), str)
    )


def _receipt_path(backup_dir: Path, receipt_root: Path | None) -> Path:
    return (
        receipt_root / f"{backup_dir.name}.json"
        if receipt_root is not None
        else backup_dir / RECEIPT_NAME
    )


def _atomic_write_receipt(target: Path, receipt: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, target)


def _load_local_receipt(
    backup_dir: Path, receipt_root: Path | None = None
) -> dict[str, Any] | None:
    receipt_path = _receipt_path(backup_dir, receipt_root)
    if not receipt_path.is_file():
        return None
    receipt = load_manifest_file(receipt_path, "offsite receipt")
    manifest_sha = sha256_file(backup_dir / "manifest.json")
    if not _receipt_matches(receipt, backup_dir.name, manifest_sha):
        fail(f"local offsite receipt does not match backup: {backup_dir}")
    return receipt


def _recover_remote_receipt(
    client: WebDAVClient,
    backup_dir: Path,
    manifest_sha: str,
    remote_archive: str,
    remote_receipt: str,
    staging_dir: Path,
    local_receipt_path: Path,
) -> dict[str, Any] | None:
    receipt = client.get_json(remote_receipt)
    if receipt is None:
        return None
    if not _receipt_matches(
        receipt,
        backup_dir.name,
        manifest_sha,
        remote_archive=remote_archive,
    ):
        fail(f"remote receipt conflicts with local backup: {remote_receipt}")
    downloaded = staging_dir / f"{backup_dir.name}.remote.age"
    client.download_file(str(receipt["remote_archive_path"]), downloaded)
    if (
        sha256_file(downloaded) != receipt["encrypted_sha256"]
        or downloaded.stat().st_size != receipt["encrypted_size_bytes"]
    ):
        fail(f"remote encrypted backup checksum mismatch: {receipt['remote_archive_path']}")
    _atomic_write_receipt(local_receipt_path, receipt)
    return receipt


def export_snapshot(
    *,
    backup_dir: Path,
    staging_dir: Path,
    remote_prefix: str,
    age_recipient: str,
    client: WebDAVClient,
    receipt_root: Path | None = None,
) -> dict[str, Any]:
    _manifest, files = validate_backup_snapshot(backup_dir)
    manifest_sha = sha256_file(backup_dir / "manifest.json")
    remote_archive, remote_receipt = _receipt_paths(backup_dir, remote_prefix)
    recovered = _recover_remote_receipt(
        client,
        backup_dir,
        manifest_sha,
        remote_archive,
        remote_receipt,
        staging_dir,
        _receipt_path(backup_dir, receipt_root),
    )
    if recovered is not None:
        return {"snapshot_id": backup_dir.name, "status": "recovered", "receipt": recovered}
    if client.exists(remote_archive):
        fail(f"remote archive exists without a matching receipt: {remote_archive}")

    plaintext = staging_dir / f"{backup_dir.name}.tar.gz"
    encrypted = staging_dir / f"{backup_dir.name}.tar.gz.age"
    try:
        create_snapshot_archive(backup_dir, files, plaintext)
        run_age_encrypt(plaintext, encrypted, age_recipient)
    finally:
        plaintext.unlink(missing_ok=True)
    receipt = _build_receipt(backup_dir, manifest_sha, encrypted, remote_archive)
    client.ensure_directories(remote_archive)
    client.upload_file(encrypted, remote_archive)
    downloaded = staging_dir / f"{backup_dir.name}.roundtrip.age"
    client.download_file(remote_archive, downloaded)
    if (
        sha256_file(downloaded) != receipt["encrypted_sha256"]
        or downloaded.stat().st_size != receipt["encrypted_size_bytes"]
    ):
        fail(f"remote encrypted backup checksum mismatch after upload: {remote_archive}")
    client.upload_json_once(receipt, remote_receipt)
    _atomic_write_receipt(_receipt_path(backup_dir, receipt_root), receipt)
    encrypted.unlink(missing_ok=True)
    downloaded.unlink(missing_ok=True)
    return {"snapshot_id": backup_dir.name, "status": "exported", "receipt": receipt}


def run_server_export_backups(
    *,
    backup_root: str,
    staging_dir: str,
    webdav_url: str,
    remote_prefix: str,
    receipt_root: str = "",
    age_recipient: str,
    auth_mode: str,
    user_env: str,
    secret_env: str,
    as_json: bool = False,
    client: WebDAVClient | None = None,
) -> int:
    root = Path(backup_root).resolve()
    if not root.is_dir():
        fail(f"backup root is not a directory: {root}")
    staging = Path(staging_dir).resolve()
    staging.mkdir(parents=True, exist_ok=True)
    staging.chmod(0o700)
    snapshots, _ignored = classify_backup_entries(root)
    receipts = Path(receipt_root).resolve() if receipt_root else None
    if receipts is not None:
        receipts.mkdir(parents=True, exist_ok=True)
        receipts.chmod(0o700)
    pending = [path for path in snapshots if _load_local_receipt(path, receipts) is None]
    owned_client = client is None
    active_client = client or _client_from_environment(
        base_url=webdav_url,
        auth_mode=auth_mode,
        user_env=user_env,
        secret_env=secret_env,
    )
    try:
        exported = [
            export_snapshot(
                backup_dir=path,
                staging_dir=staging,
                remote_prefix=remote_prefix,
                age_recipient=age_recipient,
                client=active_client,
                receipt_root=receipts,
            )
            for path in pending
        ]
    finally:
        if owned_client:
            active_client.close()
    summary = {"ok": True, "backup_root": str(root), "pending": len(pending), "exports": exported}
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"OK: exported {len(exported)} pending backup(s)")
    return 0


def _safe_extract_snapshot(archive_path: Path, output_dir: Path) -> Path:
    backup_dir = output_dir / "backup"
    backup_dir.mkdir(mode=0o700)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        if "manifest.json" not in names or len(names) != 4:
            fail("offsite archive must contain exactly one manifest and three backup files")
        for member in members:
            if not member.isfile() or PurePosixPath(member.name).name != member.name:
                fail(f"offsite archive contains an unsafe member: {member.name}")
        archive.extractall(backup_dir, members=members, filter="data")
    return backup_dir


def run_server_verify_offsite_backup(
    *,
    backup_dir: str,
    output_dir: str,
    webdav_url: str,
    auth_mode: str,
    user_env: str,
    secret_env: str,
    age_identity: str,
    receipt_root: str = "",
    as_json: bool = False,
    client: WebDAVClient | None = None,
) -> int:
    source = Path(backup_dir).resolve()
    receipts = Path(receipt_root).resolve() if receipt_root else None
    receipt = _load_local_receipt(source, receipts)
    if receipt is None:
        fail(f"backup has no offsite receipt: {source}")
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        fail(f"restore rehearsal output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    owned_client = client is None
    active_client = client or _client_from_environment(
        base_url=webdav_url,
        auth_mode=auth_mode,
        user_env=user_env,
        secret_env=secret_env,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="infinitas-offsite-verify-") as temp:
            temp_dir = Path(temp)
            encrypted = temp_dir / "snapshot.tar.gz.age"
            active_client.download_file(str(receipt["remote_archive_path"]), encrypted)
            if (
                sha256_file(encrypted) != receipt["encrypted_sha256"]
                or encrypted.stat().st_size != receipt["encrypted_size_bytes"]
            ):
                fail("downloaded offsite backup checksum does not match its receipt")
            plaintext = temp_dir / "snapshot.tar.gz"
            run_age_decrypt(encrypted, plaintext, Path(age_identity).resolve())
            restored_backup = _safe_extract_snapshot(plaintext, temp_dir)
            validate_backup_snapshot(restored_backup)
            with redirect_stdout(io.StringIO()):
                run_server_restore_rehearsal(
                    backup_dir=str(restored_backup), output_dir=str(output), as_json=False
                )
    finally:
        if owned_client:
            active_client.close()
    summary = {"ok": True, "snapshot_id": source.name, "restore_output": str(output)}
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"OK: verified and rehearsed offsite backup {source.name}")
    return 0


def load_manifest_file(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid {label} at {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must contain an object: {path}")
    return payload


def _age_seconds(timestamp: str, now: datetime) -> float:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        fail(f"invalid backup timestamp: {timestamp}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds())


def run_server_inspect_backup_state(
    *,
    backup_root: str,
    max_local_age_hours: float,
    max_offsite_age_hours: float,
    receipt_root: str = "",
    as_json: bool = False,
) -> int:
    root = Path(backup_root).resolve()
    if not root.is_dir():
        fail(f"backup root is not a directory: {root}")
    snapshots, _ignored = classify_backup_entries(root)
    snapshots = sorted(snapshots, key=lambda path: path.name, reverse=True)
    receipts_root = Path(receipt_root).resolve() if receipt_root else None
    now = datetime.now(timezone.utc)
    local_age = None
    if snapshots:
        local_manifest = load_manifest(snapshots[0])
        local_age = _age_seconds(str(local_manifest.get("created_at", "")), now)
    receipts = []
    for snapshot in snapshots:
        receipt = _load_local_receipt(snapshot, receipts_root)
        if receipt is not None:
            receipts.append(receipt)
    receipts.sort(key=lambda item: str(item.get("completed_at", "")), reverse=True)
    offsite_age = _age_seconds(str(receipts[0].get("completed_at", "")), now) if receipts else None
    alerts = []
    if local_age is None or local_age > max_local_age_hours * 3600:
        alerts.append("local_backup_stale")
    if offsite_age is None or offsite_age > max_offsite_age_hours * 3600:
        alerts.append("offsite_backup_stale")
    summary = {
        "ok": not alerts,
        "backup_root": str(root),
        "latest_local_age_seconds": local_age,
        "latest_offsite_age_seconds": offsite_age,
        "pending_exports": len(snapshots) - len(receipts),
        "alerts": alerts,
    }
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"{'OK' if not alerts else 'ALERT'}: backups pending={summary['pending_exports']} "
            f"local_age={local_age} offsite_age={offsite_age}"
        )
    return 0 if not alerts else 2


__all__ = [
    "RECEIPT_NAME",
    "WebDAVClient",
    "create_snapshot_archive",
    "export_snapshot",
    "run_server_export_backups",
    "run_server_inspect_backup_state",
    "run_server_verify_offsite_backup",
    "validate_backup_snapshot",
]
