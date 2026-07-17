from __future__ import annotations

import io
import tarfile
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


def _link_member(name: str, linkname: str, member_type: bytes) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = member_type
    member.linkname = linkname
    return member
