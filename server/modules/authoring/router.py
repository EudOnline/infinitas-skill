from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi import Path as PathParam
from sqlalchemy.orm import Session

import server.modules.authoring.service as service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.authoring.content import MAX_BUNDLE_BYTES, ContentValidationError
from server.modules.authoring.schemas import (
    SkillContentView,
    SkillCreateRequest,
    SkillVersionCreateRequest,
    SkillVersionView,
    SkillView,
)
from server.modules.identity.auth import get_current_access_context
from server.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["authoring"])


# Common error responses for authoring endpoints so OpenAPI stays honest.
_AUTHORING_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not authenticated"},
    403: {"description": "Forbidden"},
    404: {"description": "Skill not found"},
}

_CONTENT_ERROR_RESPONSES = {
    **_AUTHORING_ERROR_RESPONSES,
    413: {"description": "Content bundle exceeds the upload size limit"},
    415: {"description": "Unsupported content type"},
    422: {"description": "Invalid or non-installable content bundle"},
}


async def _read_bundle_body(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type not in {"application/gzip", "application/x-gzip"}:
        raise HTTPException(status_code=415, detail="content type must be application/gzip")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid content-length header") from exc
        if declared_size > MAX_BUNDLE_BYTES:
            raise HTTPException(status_code=413, detail="content bundle exceeds upload size limit")
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_BUNDLE_BYTES:
            raise HTTPException(status_code=413, detail="content bundle exceeds upload size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _require_authoring_principal(context: AccessContext) -> int:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(
        context,
        {"api:user", "authoring:write", "skill:write", "registry:publish"},
    ):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id


def _require_product_object_scope(context: AccessContext, skill_id: int | None) -> None:
    if context.credential.type != "product_token":
        return
    if context.credential.product_token_type != "publisher":  # noqa: S105
        raise HTTPException(status_code=403, detail="publisher token required")
    if skill_id is None:
        raise HTTPException(
            status_code=403,
            detail="object-scoped publisher tokens cannot create new objects",
        )
    if context.credential.product_object_id != skill_id:
        raise HTTPException(status_code=403, detail="publisher token object scope mismatch")


@router.post("/skills", response_model=SkillView, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillView:
    principal_id = _require_authoring_principal(context)
    _require_product_object_scope(context, None)
    try:
        skill = service.create_skill(
            db,
            namespace_id=principal_id,
            actor_principal_id=principal_id,
            payload=payload,
        )
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillView.from_model(skill)


@router.post(
    "/skills/{skill_id}/content",
    response_model=SkillContentView,
    status_code=status.HTTP_201_CREATED,
    responses=_CONTENT_ERROR_RESPONSES,
)
async def upload_content(
    request: Request,
    skill_id: int = PathParam(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillContentView:
    principal_id = _require_authoring_principal(context)
    _require_product_object_scope(context, skill_id)
    raw_bundle = await _read_bundle_body(request)
    settings = get_settings()
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        content = service.upload_skill_content(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            raw_bundle=raw_bundle,
            artifact_root=settings.artifact_path,
            repo_root=settings.repo_path,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ContentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SkillContentView.from_model(content)


@router.post(
    "/skills/{skill_id}/versions",
    response_model=SkillVersionView,
    status_code=status.HTTP_201_CREATED,
    responses=_AUTHORING_ERROR_RESPONSES,
)
def create_version(
    payload: SkillVersionCreateRequest,
    skill_id: int = PathParam(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillVersionView:
    principal_id = _require_authoring_principal(context)
    _require_product_object_scope(context, skill_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        skill_version = service.create_skill_version_snapshot(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
            content_public_id=payload.content_id,
            metadata=payload.metadata,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillVersionView.from_model(skill_version)


@router.get(
    "/skills/{skill_id}/versions",
    response_model=list[SkillVersionView],
    responses=_AUTHORING_ERROR_RESPONSES,
)
def list_versions(
    skill_id: int = PathParam(gt=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> list[SkillVersionView]:
    principal_id = _require_authoring_principal(context)
    _require_product_object_scope(context, skill_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        versions = service.list_skill_versions(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            limit=limit,
            offset=offset,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [SkillVersionView.from_model(version) for version in versions]


@router.get(
    "/skills/{skill_id}",
    response_model=SkillView,
    responses=_AUTHORING_ERROR_RESPONSES,
)
def get_skill(
    skill_id: int = PathParam(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillView:
    principal_id = _require_authoring_principal(context)
    _require_product_object_scope(context, skill_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        skill = service.get_skill_or_404(db, skill_id)
        service.assert_namespace_owner(
            db,
            skill,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillView.from_model(skill)
