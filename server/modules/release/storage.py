from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from server.artifact_ops import ensure_file_bytes, ensure_file_copy, sha256_bytes


@dataclass
class StoredArtifact:
    storage_uri: str
    sha256: str
    size_bytes: int
    public_path: str


class ArtifactStorage(ABC):
    @abstractmethod
    def put_bytes(self, data: bytes, *, public_path: str) -> StoredArtifact:
        raise NotImplementedError

    @abstractmethod
    def clear_public_path(self, public_path: str) -> None:
        raise NotImplementedError


class LocalArtifactStorage(ArtifactStorage):
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_public_target(self, public_path: str) -> Path:
        candidate = (self.root / public_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"public_path escapes artifact root: {public_path!r}") from exc
        return candidate

    def put_bytes(self, data: bytes, *, public_path: str) -> StoredArtifact:
        digest = sha256_bytes(data)
        object_rel = Path("objects") / "sha256" / digest
        object_path = self.root / object_rel
        ensure_file_bytes(object_path, data)

        public_rel = Path(public_path)
        public_abspath = self._resolve_public_target(public_path)
        ensure_file_copy(object_path, public_abspath)
        return StoredArtifact(
            storage_uri=str(object_rel).replace("\\", "/"),
            sha256=digest,
            size_bytes=len(data),
            public_path=str(public_rel).replace("\\", "/"),
        )

    def clear_public_path(self, public_path: str) -> None:
        target = self._resolve_public_target(public_path)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()


def build_artifact_storage(root: Path) -> ArtifactStorage:
    return LocalArtifactStorage(root)
