from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.bootstrap import seed_bootstrap_users
from server.db import init_db, session_scope
from server.settings import Settings, get_settings


def ensure_database_ready(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    init_db()
    if resolved_settings.bootstrap_users:
        with session_scope() as session:
            seed_bootstrap_users(session, resolved_settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_database_ready(app.state.settings)
    yield
