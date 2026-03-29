from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from server.auth import AUTH_COOKIE_NAME
from server.db import get_db
from server.modules.access.authn import resolve_access_context
from server.modules.discovery import service as discovery_service
from server.settings import get_settings

router = APIRouter(prefix="/api/search", tags=["search"])


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _search_payload(entries) -> dict:
    return {
        "skills": [
            {
                "id": entry.qualified_name,
                "name": entry.display_name or entry.name,
                "qualified_name": entry.qualified_name,
                "summary": entry.summary or "",
                "version": entry.version,
                "icon": "🎯",
            }
            for entry in entries
        ],
        "commands": [],
    }


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _catalog_search_roots() -> list[Path]:
    settings = get_settings()
    return [
        settings.artifact_path,
        settings.artifact_path / "catalog",
        settings.root_dir / "catalog",
    ]


def _load_catalog_search_entries() -> list[dict]:
    for root in _catalog_search_roots():
        payload = _read_json(root / "discovery-index.json")
        skills = payload.get("skills")
        if isinstance(skills, list):
            return [item for item in skills if isinstance(item, dict)]
    return []


def _catalog_entry_score(query: str, item: dict) -> float:
    needle = str(query or "").strip().lower()
    if not needle:
        return 1.0

    haystacks = [
        item.get("name") or "",
        item.get("qualified_name") or "",
        item.get("summary") or "",
        item.get("latest_version") or "",
    ]
    haystacks.extend(item.get("match_names") or [])
    haystacks.extend(item.get("tags") or [])

    score = 0.0
    for index, raw in enumerate(haystacks):
        value = str(raw or "").strip().lower()
        if not value:
            continue
        if value == needle:
            score += 100.0 - index
        elif value.startswith(needle):
            score += 60.0 - index
        elif needle in value:
            score += 30.0 - index
    return score


def _search_catalog_snapshot(*, query: str, limit: int) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    for item in _load_catalog_search_entries():
        score = _catalog_entry_score(query, item)
        if score <= 0:
            continue
        scored.append((score, item))
    scored.sort(
        key=lambda pair: (
            -pair[0],
            str(pair[1].get("qualified_name") or ""),
            str(pair[1].get("latest_version") or ""),
        )
    )
    return [
        {
            "id": item.get("qualified_name") or item.get("name") or "",
            "name": item.get("qualified_name") or item.get("name") or "",
            "qualified_name": item.get("qualified_name") or item.get("name") or "",
            "summary": item.get("summary") or "",
            "version": item.get("latest_version") or item.get("default_install_version") or "",
            "icon": "🎯",
        }
        for _score, item in scored[:limit]
    ]


@router.get("")
def search_registry(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=8, ge=1, le=20),
    scope: str = Query(default="public", pattern="^(public|me)$"),
    db: Session = Depends(get_db),
):
    token = _extract_bearer_token(request.headers.get("authorization")) or request.cookies.get(AUTH_COOKIE_NAME)
    if scope == "me":
        if not token:
            raise HTTPException(status_code=401, detail="search requires authentication")
        context = resolve_access_context(db, token, allow_user_bridge=True)
        if context is None:
            raise HTTPException(status_code=401, detail="search requires authentication")
        entries = discovery_service.search_me_catalog(db, context=context, query=q, limit=limit)
        return _search_payload(entries)

    snapshot_entries = _search_catalog_snapshot(query=q, limit=limit)
    if snapshot_entries:
        return {"skills": snapshot_entries, "commands": []}

    entries = discovery_service.search_public_catalog(db, query=q, limit=limit)
    return _search_payload(entries)
