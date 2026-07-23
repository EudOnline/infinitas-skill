from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi import Path as PathParam
from sqlalchemy.orm import Session

import server.modules.authoring.service as service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.access.credential_policy import (
    CredentialPolicyForbidden,
    assert_credential_mutation_allowed,
)
from server.modules.access.product_scope import (
    ProductScopeForbidden,
    assert_product_token_skill_scope,
)
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
    429: {"description": "Pending content quota exceeded"},
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


def _require_product_scope(
    context: AccessContext,
    db: Session,
    skill_id: int | None,
    *,
    allow_create: bool = False,
) -> None:
    try:
        assert_product_token_skill_scope(
            db,
            context=context,
            skill_id=skill_id,
            allow_create=allow_create,
        )
    except ProductScopeForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_credential_mutation(context: AccessContext, db: Session) -> None:
    try:
        assert_credential_mutation_allowed(
            db,
            credential=context.credential,
            object_kind="skill",
        )
    except CredentialPolicyForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/skills", response_model=SkillView, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillView:
    principal_id = _require_authoring_principal(context)
    _require_product_scope(context, db, None, allow_create=True)
    _require_credential_mutation(context, db)
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


@router.get("/skills", response_model=list[SkillView], responses=_AUTHORING_ERROR_RESPONSES)
def list_skills(
    slug: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> list[SkillView]:
    principal_id = _require_authoring_principal(context)
    if (
        context.credential.type == "product_token"
        and context.credential.product_scope_type != "namespace"
    ):
        scoped_skill_id = context.credential.product_object_id
        _require_product_scope(context, db, scoped_skill_id)
        if scoped_skill_id is None or offset:
            return []
        scoped_skill = service.get_skill_or_404(db, scoped_skill_id)
        if slug is not None and scoped_skill.slug != slug:
            return []
        return [SkillView.from_model(scoped_skill)]
    _require_product_scope(context, db, None, allow_create=True)
    return [
        SkillView.from_model(skill)
        for skill in service.list_skills(
            db,
            namespace_id=principal_id,
            slug=slug,
            limit=limit,
            offset=offset,
        )
    ]


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
    _require_product_scope(context, db, skill_id)
    _require_credential_mutation(context, db)
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
            pending_ttl_hours=settings.content_pending_ttl_hours,
            max_pending_per_skill=settings.content_max_pending_per_skill,
            max_pending_bytes_per_principal=(settings.content_max_pending_bytes_per_principal),
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ContentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.ContentQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
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
    _require_product_scope(context, db, skill_id)
    _require_credential_mutation(context, db)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    settings = get_settings()
    try:
        skill_version = service.create_skill_version_snapshot(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
            content_public_id=payload.content_id,
            pending_ttl_hours=settings.content_pending_ttl_hours,
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
    _require_product_scope(context, db, skill_id)
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
    "/skills/{skill_id}/versions/{version}",
    response_model=SkillVersionView,
    responses=_AUTHORING_ERROR_RESPONSES,
)
def get_version(
    skill_id: int = PathParam(gt=0),
    version: str = PathParam(min_length=5, max_length=64),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillVersionView:
    principal_id = _require_authoring_principal(context)
    _require_product_scope(context, db, skill_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        found = service.get_skill_version(
            db,
            skill_id=skill_id,
            version=version,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillVersionView.from_model(found)


@router.post(
    "/skills/{skill_id}/archive",
    response_model=SkillView,
    responses=_AUTHORING_ERROR_RESPONSES,
)
def archive_skill(
    skill_id: int = PathParam(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> SkillView:
    principal_id = _require_authoring_principal(context)
    _require_product_scope(context, db, skill_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        skill = service.archive_skill(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillView.from_model(skill)


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
    _require_product_scope(context, db, skill_id)
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
