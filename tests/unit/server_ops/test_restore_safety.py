from __future__ import annotations

import io
import sqlite3
import subprocess
import tarfile
from contextlib import closing
from pathlib import Path

import pytest

from infinitas_skill.server import restore as RESTORE


def _add_file(archive: tarfile.TarFile, name: str, content: bytes = b"data") -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def _write_archive(path: Path, malicious_member: tarfile.TarInfo) -> None:
    with tarfile.open(path, "w:gz") as archive:
        _add_file(archive, "artifacts/ai-index.json", b"{}")
        _add_file(archive, "artifacts/catalog/catalog.json", b"{}")
        archive.addfile(malicious_member)


@pytest.mark.parametrize(
    "member_factory",
    [
        lambda tmp_path: tarfile.TarInfo("../escaped.txt"),
        lambda tmp_path: tarfile.TarInfo(str(tmp_path / "absolute-escaped.txt")),
        lambda _tmp_path: _link_member("artifacts/link", "../../escaped", tarfile.SYMTYPE),
        lambda _tmp_path: _link_member("artifacts/link", "../../escaped", tarfile.LNKTYPE),
    ],
    ids=["parent-traversal", "absolute-path", "symlink", "hardlink"],
)
def test_extract_artifacts_rejects_unsafe_members(tmp_path: Path, member_factory) -> None:
    archive_path = tmp_path / "artifacts.tar.gz"
    output_dir = tmp_path / "restore"
    output_dir.mkdir()
    malicious_member = member_factory(tmp_path)
    _write_archive(archive_path, malicious_member)

    with pytest.raises(SystemExit, match="1"):
        RESTORE.extract_artifacts(archive_path, output_dir)

    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "absolute-escaped.txt").exists()


def test_extract_artifacts_accepts_regular_backup(tmp_path: Path) -> None:
    archive_path = tmp_path / "artifacts.tar.gz"
    output_dir = tmp_path / "restore"
    output_dir.mkdir()
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_file(archive, "artifacts/ai-index.json", b"{}")
        _add_file(archive, "artifacts/catalog/catalog.json", b"{}")

    artifacts_dir = RESTORE.extract_artifacts(archive_path, output_dir)

    assert artifacts_dir == output_dir / "artifacts"
    assert (artifacts_dir / "ai-index.json").read_text(encoding="utf-8") == "{}"


def test_verify_backup_checksums_rejects_missing_or_changed_files(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    bundle = backup_dir / "repo.bundle"
    bundle.write_bytes(b"original")

    with pytest.raises(SystemExit, match="1"):
        RESTORE.verify_backup_checksums(backup_dir, {}, [bundle])

    manifest = {"schema_version": 1, "checksums": {"repo.bundle": "0" * 64}}
    with pytest.raises(SystemExit, match="1"):
        RESTORE.verify_backup_checksums(backup_dir, manifest, [bundle])


def test_verify_bundle_works_outside_a_git_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test User"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True
    )
    (source / "README.md").write_text("bundle test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "test"], check=True)
    bundle = tmp_path / "repo.bundle"
    subprocess.run(["git", "-C", str(source), "bundle", "create", str(bundle), "--all"], check=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    RESTORE.verify_bundle(bundle)


def test_copy_and_verify_sqlite_runs_full_integrity_check(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("CREATE TABLE entries (value TEXT NOT NULL)")
        connection.execute("INSERT INTO entries VALUES ('restored')")
        connection.commit()

    RESTORE.copy_and_verify_sqlite(source, target)

    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("SELECT value FROM entries").fetchall() == [("restored",)]
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_copy_and_verify_sqlite_rejects_corrupt_database(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.db"
    source.write_bytes(b"not a sqlite database")

    with pytest.raises(SystemExit, match="1"):
        RESTORE.copy_and_verify_sqlite(source, tmp_path / "restored.db")


def _link_member(name: str, linkname: str, member_type: bytes) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = member_type
    member.linkname = linkname
    return member
