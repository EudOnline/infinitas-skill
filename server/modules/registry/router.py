from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import server.modules.registry.service as service
from server.db import get_db
from server.modules.registry.schemas import (
    RegistryAIIndexView,
    RegistryCompatibilityView,
    RegistryDiscoveryView,
    RegistryDistributionsView,
)
from server.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])


def _file_response(artifact_root: Path, relative_path: str) -> FileResponse:
    artifact_root = artifact_root.resolve()
    candidate = (artifact_root / relative_path).resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(candidate)


def _payload(
    builder: Callable[[Settings, Session, Request], dict[str, Any]],
    request: Request,
    db: Session,
) -> dict[str, Any]:
    try:
        result: dict[str, Any] = builder(get_settings(), db, request)
        return result
    except service.UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/ai-index.json", response_model=RegistryAIIndexView)
def registry_ai_index(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _payload(service.build_registry_ai_index_payload, request, db)


@router.get("/discovery-index.json", response_model=RegistryDiscoveryView)
def registry_discovery_index(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _payload(service.build_registry_discovery_payload, request, db)


@router.get("/distributions.json", response_model=RegistryDistributionsView)
def registry_distributions(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _payload(service.build_registry_distributions_payload, request, db)


@router.get("/compatibility.json", response_model=RegistryCompatibilityView)
def registry_compatibility(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _payload(service.build_registry_compatibility_payload, request, db)


@router.get("/{registry_path:path}")
def registry_artifact(
    registry_path: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        relative_path = service.resolve_registry_artifact_relative_path(
            get_settings(),
            db,
            request,
            registry_path,
        )
    except service.UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _file_response(get_settings().artifact_path, relative_path)
