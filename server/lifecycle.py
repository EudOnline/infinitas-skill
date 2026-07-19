from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.bootstrap import seed_bootstrap_users
from server.db import init_db, session_scope
from server.jobs import enqueue_job, has_active_job
from server.settings import Settings, get_settings


def ensure_database_ready(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    init_db()
    if resolved_settings.bootstrap_users:
        with session_scope() as session:
            seed_bootstrap_users(session, resolved_settings)
    if resolved_settings.environment == "production":
        with session_scope() as session:
            if not has_active_job(session, kind="prune_skill_contents"):
                enqueue_job(
                    session,
                    kind="prune_skill_contents",
                    payload={"limit": 1000},
                    requested_by=None,
                    note="prune expired pending skill content",
                )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_database_ready(app.state.settings)
    yield
