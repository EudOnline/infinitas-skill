from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from infinitas_skill.openclaw.runtime_model import build_openclaw_runtime_model
from infinitas_skill.root import ROOT
from server.auth import maybe_get_current_access_context
from server.db import get_db
from server.modules.discovery import service as discovery_service
from server.settings import get_settings

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _publisher_from_qualified_name(qualified_name: str) -> str:
    publisher, _, _name = str(qualified_name or "").partition("/")
    return publisher


def _install_ref(qualified_name: str, version: str) -> str:
    base_ref = str(qualified_name or "").strip()
    resolved_version = str(version or "").strip()
    if not resolved_version:
        return base_ref
    return f"{base_ref}@{resolved_version}"


@lru_cache(maxsize=1)
def _search_runtime_defaults() -> tuple[dict, str, list[str]]:
    runtime_model = build_openclaw_runtime_model(ROOT)
    runtime_targets = list(runtime_model.get("skill_dir_candidates") or [])
    workspace_targets = [
        target
        for target in runtime_targets
        if isinstance(target, str)
        and target
        and not target.startswith("~/")
        and not Path(target).is_absolute()
    ]
    capabilities = dict(runtime_model.get("capabilities") or {})
    runtime = {
        "platform": "openclaw",
        "source_mode": "hosted-registry-release",
        "workspace_scope": "workspace",
        "workspace_targets": runtime_targets,
        "install_targets": {
            "workspace": workspace_targets,
            "shared": [
                target
                for target in runtime_targets
                if isinstance(target, str) and target and target not in workspace_targets
            ],
        },
        "plugin_capabilities": {},
        "background_tasks": {"required": False},
        "subagents": {"required": False},
        "readiness": {
            "ready": True,
            "supports_background_tasks": capabilities.get("supports_background_tasks") is True,
            "supports_plugins": capabilities.get("supports_plugins") is True,
            "supports_subagents": capabilities.get("supports_subagents") is True,
            "status": "ready",
        },
    }
    return runtime, "ready", workspace_targets


def _search_skill_payload(
    *,
    scope: str,
    qualified_name: str,
    name: str,
    summary: str,
    version: str,
    audience_type: str,
    listing_mode: str,
    install_api_path: str | None = None,
    runtime: dict | None = None,
    runtime_readiness: str | None = None,
    workspace_targets: list[str] | None = None,
) -> dict:
    install_ref = _install_ref(qualified_name, version)
    payload = {
        "id": qualified_name,
        "name": name,
        "qualified_name": qualified_name,
        "summary": summary,
        "version": version,
        "icon": "🎯",
        "publisher": _publisher_from_qualified_name(qualified_name),
        "audience_type": audience_type,
        "listing_mode": listing_mode,
        "install_scope": scope,
        "install_ref": install_ref,
    }
    if isinstance(install_api_path, str) and install_api_path:
        payload["install_api_path"] = install_api_path
    if isinstance(runtime, dict) and runtime:
        payload["runtime"] = runtime
    if isinstance(runtime_readiness, str) and runtime_readiness.strip():
        payload["runtime_readiness"] = runtime_readiness
    if isinstance(workspace_targets, list):
        payload["workspace_targets"] = [item for item in workspace_targets if isinstance(item, str)]
    return payload


def _search_payload(entries, *, scope: str) -> dict:
    runtime, runtime_readiness, workspace_targets = _search_runtime_defaults()
    return {
        "skills": [
            _search_skill_payload(
                scope=scope,
                qualified_name=entry.qualified_name,
                name=entry.display_name or entry.name,
                summary=entry.summary or "",
                version=entry.version,
                audience_type=entry.audience_type,
                listing_mode=entry.listing_mode,
                install_api_path=(
                    f"/api/v1/install/{scope}/"
                    f"{_install_ref(entry.qualified_name, entry.version)}"
                ),
                runtime=runtime,
                runtime_readiness=runtime_readiness,
                workspace_targets=workspace_targets,
            )
            for entry in entries
        ],
        "commands": [],
    }


def _effective_search_scope(*, requested_scope: str, has_grant_credential: bool) -> str:
    if requested_scope == "me" and has_grant_credential:
        return "grant"
    return requested_scope


def _snapshot_skill_payloads(items: list[dict], *, limit: int) -> list[dict]:
    runtime, runtime_readiness, workspace_targets = _search_runtime_defaults()
    results = []
    for item in items[:limit]:
        qualified_name = item.get("qualified_name") or item.get("name") or ""
        version = item.get("latest_version") or item.get("default_install_version") or ""
        results.append(
            _search_skill_payload(
                scope="public",
                qualified_name=qualified_name,
                name=item.get("display_name") or item.get("name") or qualified_name,
                summary=item.get("summary") or "",
                version=version,
                audience_type="public",
                listing_mode="listed",
                install_api_path=(
                    "/api/v1/install/public/"
                    + _install_ref(qualified_name, version)
                ),
                runtime=item.get("runtime") if isinstance(item.get("runtime"), dict) else None,
                runtime_readiness=item.get("runtime_readiness"),
                workspace_targets=item.get("workspace_targets")
                if isinstance(item.get("workspace_targets"), list)
                else None,
            )
        )
    return results


@router.get("")
def search_registry(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=8, ge=1, le=20),
    scope: str = Query(default="public", pattern="^(public|me|grant)$"),
    db: Session = Depends(get_db),
):
    if scope in {"me", "grant"}:
        context = maybe_get_current_access_context(request, db)
        if context is None:
            raise HTTPException(status_code=401, detail="search requires authentication")
        effective_scope = _effective_search_scope(
            requested_scope=scope,
            has_grant_credential=context.credential.grant_id is not None,
        )
        try:
            if effective_scope == "grant":
                entries = discovery_service.search_grant_catalog(
                    db, context=context, query=q, limit=limit
                )
                return _search_payload(entries, scope="grant")
            entries = discovery_service.search_me_catalog(db, context=context, query=q, limit=limit)
            return _search_payload(entries, scope="me")
        except discovery_service.ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    snapshot_items = discovery_service.search_catalog_snapshot(query=q, limit=limit)
    if snapshot_items:
        return {"skills": _snapshot_skill_payloads(snapshot_items, limit=limit), "commands": []}

    entries = discovery_service.search_public_catalog(db, query=q, limit=limit)
    return _search_payload(entries, scope="public")
