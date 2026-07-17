from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.distribution_materialization import safely_extract_bundle


def _write_bundle(path: Path, members: list[tarfile.TarInfo]) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for member in members:
            content = b"# fixture\n" if member.isfile() else None
            archive.addfile(member, io.BytesIO(content) if content is not None else None)


def _file_member(name: str) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.size = len(b"# fixture\n")
    member.mode = 0o6755
    return member


def test_safely_extract_bundle_uses_explicit_data_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    _write_bundle(bundle, [_file_member("demo-skill/SKILL.md")])
    filters: list[object] = []
    original_extractall = tarfile.TarFile.extractall

    def recording_extractall(self, path=".", members=None, *, numeric_owner=False, filter=None):
        filters.append(filter)
        return original_extractall(
            self,
            path,
            members=members,
            numeric_owner=numeric_owner,
            filter=filter,
        )

    monkeypatch.setattr(tarfile.TarFile, "extractall", recording_extractall)

    extracted = safely_extract_bundle(bundle, tmp_path / "output", expected_root="demo-skill")

    assert filters == ["data"]
    assert (extracted / "SKILL.md").read_text(encoding="utf-8") == "# fixture\n"
    assert (extracted / "SKILL.md").stat().st_mode & 0o6000 == 0


@pytest.mark.parametrize("member_name", ["../escaped.txt", "/tmp/escaped.txt"])
def test_safely_extract_bundle_rejects_paths_outside_destination(
    tmp_path: Path, member_name: str
) -> None:
    bundle = tmp_path / "unsafe.tar.gz"
    _write_bundle(bundle, [_file_member(member_name)])

    with pytest.raises(DistributionError, match="unsafe bundle member path"):
        safely_extract_bundle(bundle, tmp_path / "output")


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_safely_extract_bundle_rejects_links(tmp_path: Path, member_type: bytes) -> None:
    bundle = tmp_path / "link.tar.gz"
    member = tarfile.TarInfo("demo-skill/link")
    member.type = member_type
    member.linkname = "../../escaped.txt"
    _write_bundle(bundle, [member])

    with pytest.raises(DistributionError, match="symlink in bundle is not allowed"):
        safely_extract_bundle(bundle, tmp_path / "output")
