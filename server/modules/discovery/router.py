from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.discovery import service
from server.modules.discovery.schemas import (
    CatalogEntryView,
    CatalogListView,
    InstallResolutionView,
    ProjectionArtifactPaths,
)
from server.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["discovery"])


def _artifact_response(artifact_root: Path, relative_path: str) -> FileResponse:
    artifact_root = artifact_root.resolve()
    candidate = (artifact_root / relative_path).resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(candidate)


def _install_links(request: Request) -> ProjectionArtifactPaths:
    def _relative_path(artifact: str) -> str:
        base = request.url.path
        return f"{base}?artifact={artifact}"

    return ProjectionArtifactPaths(
        manifest_download_path=_relative_path("manifest"),
        bundle_download_path=_relative_path("bundle"),
        provenance_download_path=_relative_path("provenance"),
        signature_download_path=_relative_path("signature"),
        manifest_url=str(request.url.include_query_params(artifact="manifest")),
        bundle_url=str(request.url.include_query_params(artifact="bundle")),
        provenance_url=str(request.url.include_query_params(artifact="provenance")),
        signature_url=str(request.url.include_query_params(artifact="signature")),
    )


def _install_payload(request: Request, entry) -> InstallResolutionView:
    links = _install_links(request)
    ready_at = None
    if entry.ready_at is not None:
        ready_at = entry.ready_at.isoformat().replace("+00:00", "Z")
    return InstallResolutionView(
        exposure_id=entry.exposure_id,
        release_id=entry.release_id,
        audience_type=entry.audience_type,
        name=entry.name,
        qualified_name=entry.qualified_name,
        publisher=entry.publisher,
        version=entry.version,
        display_name=entry.display_name,
        summary=entry.summary,
        ready_at=ready_at,
        manifest_path=entry.manifest_path,
        bundle_path=entry.bundle_path,
        provenance_path=entry.provenance_path,
        signature_path=entry.signature_path,
        bundle_sha256=entry.bundle_sha256,
        manifest_download_path=links.manifest_download_path,
        bundle_download_path=links.bundle_download_path,
        provenance_download_path=links.provenance_download_path,
        signature_download_path=links.signature_download_path,
        manifest_url=links.manifest_url,
        bundle_url=links.bundle_url,
        provenance_url=links.provenance_url,
        signature_url=links.signature_url,
    )


def _catalog_list(entries) -> CatalogListView:
    return CatalogListView(
        items=[CatalogEntryView.from_projection(entry) for entry in entries],
        total=len(entries),
    )


@router.get("/catalog/public", response_model=CatalogListView)
def catalog_public(db: Session = Depends(get_db)):
    return _catalog_list(service.list_public_catalog(db))


@router.get("/catalog/me", response_model=CatalogListView)
def catalog_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        return _catalog_list(service.list_me_catalog(db, context=context))
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/catalog/grant", response_model=CatalogListView)
def catalog_grant(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        return _catalog_list(service.list_grant_catalog(db, context=context))
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/search/public", response_model=CatalogListView)
def search_public(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return _catalog_list(service.search_public_catalog(db, query=q, limit=limit))


@router.get("/search/me", response_model=CatalogListView)
def search_me(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        return _catalog_list(service.search_me_catalog(db, context=context, query=q, limit=limit))
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/search/grant", response_model=CatalogListView)
def search_grant(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        return _catalog_list(
            service.search_grant_catalog(db, context=context, query=q, limit=limit)
        )
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/install/public/{skill_ref:path}", response_model=InstallResolutionView)
def install_public(
    request: Request,
    skill_ref: str,
    artifact: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        entry = service.resolve_public_install(db, skill_ref=skill_ref)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if artifact:
        return _artifact_response(
            get_settings().artifact_path,
            service.artifact_relative_path(entry, artifact=artifact),
        )
    return _install_payload(request, entry)


@router.get("/install/me/{skill_ref:path}", response_model=InstallResolutionView)
def install_me(
    request: Request,
    skill_ref: str,
    artifact: str | None = Query(default=None),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        entry = service.resolve_me_install(db, context=context, skill_ref=skill_ref)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if artifact:
        return _artifact_response(
            get_settings().artifact_path,
            service.artifact_relative_path(entry, artifact=artifact),
        )
    return _install_payload(request, entry)


@router.get("/install/grant/{skill_ref:path}", response_model=InstallResolutionView)
def install_grant(
    request: Request,
    skill_ref: str,
    artifact: str | None = Query(default=None),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    try:
        entry = service.resolve_grant_install(db, context=context, skill_ref=skill_ref)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if artifact:
        return _artifact_response(
            get_settings().artifact_path,
            service.artifact_relative_path(entry, artifact=artifact),
        )
    return _install_payload(request, entry)
