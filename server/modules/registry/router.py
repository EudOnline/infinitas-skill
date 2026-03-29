from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from server.db import get_db
from server.modules.registry import service
from server.settings import get_settings

router = APIRouter(tags=["registry"])


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


def _payload(builder, request: Request, db: Session) -> dict:
    try:
        return builder(get_settings(), db, request)
    except service.UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/registry/ai-index.json")
def registry_ai_index(
    request: Request,
    db: Session = Depends(get_db),
):
    return _payload(service.build_registry_ai_index_payload, request, db)


@router.get("/registry/discovery-index.json")
def registry_discovery_index(
    request: Request,
    db: Session = Depends(get_db),
):
    return _payload(service.build_registry_discovery_payload, request, db)


@router.get("/registry/distributions.json")
def registry_distributions(
    request: Request,
    db: Session = Depends(get_db),
):
    return _payload(service.build_registry_distributions_payload, request, db)


@router.get("/registry/compatibility.json")
def registry_compatibility(
    request: Request,
    db: Session = Depends(get_db),
):
    return _payload(service.build_registry_compatibility_payload, request, db)


@router.get("/registry/{registry_path:path}")
def registry_artifact(
    registry_path: str,
    request: Request,
    db: Session = Depends(get_db),
):
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
