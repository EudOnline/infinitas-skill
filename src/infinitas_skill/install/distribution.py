"""Distribution bundle and manifest helpers."""

from __future__ import annotations

import tarfile
from gzip import GzipFile
from pathlib import Path
from typing import Any

from infinitas_skill.hashing import sha256_file
from infinitas_skill.install.distribution_core import DistributionError


def _normalized_publisher(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DistributionError("publisher must be a non-empty string")
    return value.strip()


def distribution_rel_dir(skill_name: str, version: str, *, publisher: str) -> Path:
    return (
        Path("catalog") / "distributions" / _normalized_publisher(publisher) / skill_name / version
    )


def distribution_paths(
    root: str | Path, skill_name: str, version: str, *, publisher: str
) -> dict[str, Path]:
    rel_dir = distribution_rel_dir(skill_name, version, publisher=publisher)
    base_dir = Path(root).resolve() / rel_dir
    return {
        "dir": base_dir,
        "rel_dir": rel_dir,
        "manifest": base_dir / "manifest.json",
        "manifest_rel": rel_dir / "manifest.json",
        "bundle": base_dir / "skill.tar.gz",
        "bundle_rel": rel_dir / "skill.tar.gz",
    }


def deterministic_bundle(
    skill_dir: str | Path, output_path: str | Path, root_dir: str | None = None
) -> dict[str, Any]:
    skill_dir = Path(skill_dir).resolve()
    output_path = Path(output_path).resolve()
    if root_dir is None:
        root_dir = skill_dir.name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = [path for path in sorted(skill_dir.rglob("*")) if path.is_file()]
    with output_path.open("wb") as raw_handle:
        with GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for path in files:
                    rel = path.relative_to(skill_dir)
                    arcname = str(Path(root_dir) / rel)
                    info = archive.gettarinfo(str(path), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as src:
                        archive.addfile(info, src)

    return {
        "format": "tar.gz",
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "size": output_path.stat().st_size,
        "root_dir": root_dir,
        "file_count": len(files),
    }


__all__ = [
    "distribution_rel_dir",
    "distribution_paths",
    "deterministic_bundle",
]
