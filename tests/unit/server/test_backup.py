from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
import subprocess
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import src.infinitas_skill.server.backup as backup_module
from server.repo_ops import locked_repo
from src.infinitas_skill.server.backup import (
    archive_artifacts,
    backup_lock,
    build_backup_checksums,
    build_prune_summary,
    classify_backup_entries,
    copy_sqlite_db,
    create_backup_dir,
    run_server_backup,
    sanitize_label,
)


def _create_backup_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "README.md").write_text("backup fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True)
    database = tmp_path / "server.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE entries (value TEXT NOT NULL)")
        connection.commit()
    artifacts = tmp_path / "artifacts"
    (artifacts / "catalog").mkdir(parents=True)
    (artifacts / "ai-index.json").write_text("{}\n", encoding="utf-8")
    return repo, database, artifacts, tmp_path / "backups"


class TestSanitizeLabel:
    def test_basic(self):
        assert sanitize_label("hello world") == "hello-world"

    def test_special_chars(self):
        assert sanitize_label("hello@world#test") == "hello-world-test"

    def test_leading_trailing(self):
        assert sanitize_label("---hello---") == "hello"

    def test_empty(self):
        assert sanitize_label("") == ""

    def test_whitespace_only(self):
        assert sanitize_label("   ") == ""


class TestCreateBackupDir:
    def test_creates_directory(self):
        with TemporaryDirectory() as td:
            backup_dir, timestamp = create_backup_dir(td, "test")
            assert backup_dir.exists()
            assert backup_dir.is_dir()
            assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
            assert len(timestamp) == 16  # YYYYMMDDTHHMMSSZ

    def test_no_label(self):
        with TemporaryDirectory() as td:
            backup_dir, timestamp = create_backup_dir(td, "")
            assert backup_dir.name == timestamp


class TestCopySqliteDb:
    def test_creates_consistent_online_backup(self):
        with TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            source = sqlite3.connect(db_path)
            source.execute("PRAGMA journal_mode=WAL")
            source.execute("CREATE TABLE entries (value TEXT NOT NULL)")
            source.execute("INSERT INTO entries VALUES ('committed')")
            source.commit()
            backup_dir = Path(td) / "backup"
            backup_dir.mkdir()
            try:
                result = copy_sqlite_db(db_path, backup_dir)
            finally:
                source.close()

            backup_path = backup_dir / "test.db"
            with closing(sqlite3.connect(backup_path)) as backup:
                rows = backup.execute("SELECT value FROM entries").fetchall()
                integrity = backup.execute("PRAGMA integrity_check").fetchall()

            assert result == "test.db"
            assert rows == [("committed",)]
            assert integrity == [("ok",)]
            assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600


class TestArchiveArtifacts:
    def test_creates_archive(self):
        with TemporaryDirectory() as td:
            artifact_path = Path(td) / "artifacts"
            artifact_path.mkdir()
            (artifact_path / "file.txt").write_text("content", encoding="utf-8")
            backup_dir = Path(td) / "backup"
            backup_dir.mkdir()
            result = archive_artifacts(artifact_path, backup_dir)
            assert result == "artifacts.tar.gz"
            archive_path = backup_dir / "artifacts.tar.gz"
            assert archive_path.exists()
            assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600


def test_run_server_backup_secures_every_snapshot_file(tmp_path: Path) -> None:
    repo, database, artifacts, output = _create_backup_fixture(tmp_path)

    assert (
        run_server_backup(
            repo_path=str(repo),
            database_url=f"sqlite:///{database}",
            artifact_path=str(artifacts),
            output_dir=str(output),
            label="permissions",
            as_json=True,
        )
        == 0
    )

    snapshots, ignored = classify_backup_entries(output)
    assert len(snapshots) == 1
    assert [path.name for path in ignored] == [".backup.lock"]
    snapshot = snapshots[0]
    assert stat.S_IMODE(snapshot.stat().st_mode) == 0o700
    assert {path.name for path in snapshot.iterdir()} == {
        "repo.bundle",
        "server.db",
        "artifacts.tar.gz",
        "manifest.json",
    }
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in snapshot.iterdir())
    assert stat.S_IMODE((output / ".backup.lock").stat().st_mode) == 0o600
    assert not list(output.glob("*.incomplete"))


def test_run_server_backup_removes_incomplete_snapshot_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, database, artifacts, output = _create_backup_fixture(tmp_path)

    def fail_archive(_artifact_path: Path, _backup_dir: Path) -> str:
        raise RuntimeError("simulated archive failure")

    monkeypatch.setattr(backup_module, "archive_artifacts", fail_archive)
    with pytest.raises(RuntimeError, match="simulated archive failure"):
        backup_module.run_server_backup(
            repo_path=str(repo),
            database_url=f"sqlite:///{database}",
            artifact_path=str(artifacts),
            output_dir=str(output),
        )

    assert not [path for path in output.iterdir() if path.is_dir()]


def test_backup_lock_rejects_overlapping_operation(tmp_path: Path) -> None:
    lock_path = tmp_path / "backup.lock"
    with backup_lock(lock_path):
        with pytest.raises(SystemExit) as exc_info, backup_lock(lock_path, timeout_seconds=0):
            pass
    assert exc_info.value.code == 1


def test_backup_lock_coordinates_with_runtime_repo_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "shared.lock"
    with locked_repo(lock_path):
        with pytest.raises(SystemExit), backup_lock(lock_path, timeout_seconds=0):
            pass


class TestBuildBackupChecksums:
    def test_hashes_each_named_backup_file(self):
        with TemporaryDirectory() as td:
            backup_dir = Path(td)
            (backup_dir / "repo.bundle").write_bytes(b"repo")
            (backup_dir / "server.db").write_bytes(b"database")

            checksums = build_backup_checksums(backup_dir, ["repo.bundle", "server.db"])

            assert set(checksums) == {"repo.bundle", "server.db"}
            assert all(len(checksum) == 64 for checksum in checksums.values())


class TestClassifyBackupEntries:
    def test_classifies_correctly(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            valid = root / "20240101T000000Z-test"
            valid.mkdir()
            (valid / "manifest.json").write_text("{}", encoding="utf-8")
            invalid = root / "not-a-backup"
            invalid.mkdir()
            ignored_file = root / "random.txt"
            ignored_file.write_text("hi", encoding="utf-8")
            eligible, ignored = classify_backup_entries(root)
            assert len(eligible) == 1
            assert eligible[0].name == "20240101T000000Z-test"
            assert len(ignored) == 2


class TestBuildPruneSummary:
    def test_keeps_recent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            for name in ["20240103T000000Z", "20240102T000000Z", "20240101T000000Z"]:
                d = root / name
                d.mkdir()
                (d / "manifest.json").write_text("{}", encoding="utf-8")
            summary = build_prune_summary(root, 2)
            assert len(summary["kept"]) == 2
            assert len(summary["deleted"]) == 1
            assert "20240101T000000Z" in summary["deleted"][0]

    def test_protects_snapshots_without_offsite_receipts(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            for name in ["20240103T000000Z", "20240102T000000Z", "20240101T000000Z"]:
                snapshot = root / name
                snapshot.mkdir()
                (snapshot / "manifest.json").write_text("{}", encoding="utf-8")
                if name != "20240101T000000Z":
                    receipt = {
                        "schema_version": 1,
                        "snapshot_id": name,
                        "backup_manifest_sha256": hashlib.sha256(b"{}").hexdigest(),
                    }
                    (snapshot / "offsite-receipt.json").write_text(
                        json.dumps(receipt), encoding="utf-8"
                    )

            summary = build_prune_summary(root, 1, require_offsite_receipt=True)

            assert [Path(path).name for path in summary["deleted"]] == ["20240102T000000Z"]
            assert [Path(path).name for path in summary["protected"]] == ["20240101T000000Z"]
