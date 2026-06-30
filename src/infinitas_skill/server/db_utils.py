"""Shared database utilities for CLI-side server operations.

Consolidates the duplicated ``server_engine_kwargs`` function and the
repeated open-build-dispose session pattern that previously appeared
in 6 separate files.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def server_engine_kwargs(database_url: str) -> dict[str, Any]:
    """Return SQLAlchemy engine keyword arguments appropriate for *database_url*.

    For SQLite URLs, adds ``check_same_thread=False`` to allow multi-threaded
    access.  For all other databases, returns an empty dict.
    """
    if database_url.startswith("sqlite:///"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


@contextmanager
def standalone_session(database_url: str):
    """Open a standalone database session for CLI operations.

    Creates an engine, opens a session, yields it, and disposes the engine
    on exit.  This replaces the repeated open-build-dispose pattern found
    in the ``*_ops.py`` CLI adapter files.

    Usage::

        with standalone_session(database_url) as session:
            results = session.scalars(select(Model)).all()
    """
    engine = create_engine(database_url, future=True, **server_engine_kwargs(database_url))
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
