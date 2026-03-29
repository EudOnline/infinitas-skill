from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def _replace_tree(source: Path, target: Path):
    source = Path(source).resolve()
    target = Path(target).resolve()
    if target.exists():
        shutil.rmtree(target)
    if source.exists():
        shutil.copytree(source, target)


def _merge_tree(source: Path, target: Path):
    source = Path(source).resolve()
    target = Path(target).resolve()
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _copy_or_remove(source: Path, target: Path):
    source = Path(source).resolve()
    target = Path(target).resolve()
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    if target.exists():
        target.unlink()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_file_bytes(path: Path, data: bytes):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def ensure_file_copy(source: Path, target: Path):
    source = Path(source).resolve()
    target = Path(target).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes():
        return
    shutil.copy2(source, target)


def sync_catalog_artifacts(repo_path: Path, artifact_path: Path):
    repo_path = Path(repo_path).resolve()
    artifact_path = Path(artifact_path).resolve()
    artifact_path.mkdir(parents=True, exist_ok=True)
    source_catalog = repo_path / 'catalog'
    target_catalog = artifact_path / 'catalog'
    _replace_tree(source_catalog, target_catalog)

    _copy_or_remove(source_catalog / 'ai-index.json', artifact_path / 'ai-index.json')
    _copy_or_remove(source_catalog / 'distributions.json', artifact_path / 'distributions.json')
    _copy_or_remove(source_catalog / 'compatibility.json', artifact_path / 'compatibility.json')
    _copy_or_remove(source_catalog / 'discovery-index.json', artifact_path / 'discovery-index.json')

    _merge_tree(source_catalog / 'distributions', artifact_path / 'skills')
    _merge_tree(source_catalog / 'provenance', artifact_path / 'provenance')
