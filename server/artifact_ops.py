from __future__ import annotations

import shutil
from pathlib import Path


def sync_catalog_artifacts(repo_path: Path, artifact_path: Path):
    repo_path = Path(repo_path).resolve()
    artifact_path = Path(artifact_path).resolve()
    artifact_path.mkdir(parents=True, exist_ok=True)
    source_catalog = repo_path / 'catalog'
    target_catalog = artifact_path / 'catalog'
    if target_catalog.exists():
        shutil.rmtree(target_catalog)
    shutil.copytree(source_catalog, target_catalog)

    ai_index = source_catalog / 'ai-index.json'
    discovery_index = source_catalog / 'discovery-index.json'
    if ai_index.exists():
        shutil.copy2(ai_index, artifact_path / 'ai-index.json')
    if discovery_index.exists():
        shutil.copy2(discovery_index, artifact_path / 'discovery-index.json')
