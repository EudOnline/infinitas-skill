from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from server import model_registry as _model_registry  # noqa: F401
from server.model_base import Base
from server.settings import get_settings

_ROLLBACK_ARTIFACT_PATHS = "rollback_artifact_paths"


def register_rollback_artifact_cleanup(session: Session, *, root: Path, path: str) -> None:
    resolved_root = Path(root).resolve()
    target = (resolved_root / path).resolve()
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"rollback cleanup path escapes artifact root: {path!r}") from exc
    cleanups = session.info.setdefault(_ROLLBACK_ARTIFACT_PATHS, set())
    cleanups.add((str(resolved_root), str(target)))


def _clear_rollback_artifact_cleanups(session: Session) -> None:
    info = getattr(session, "info", None)
    if isinstance(info, dict):
        info.pop(_ROLLBACK_ARTIFACT_PATHS, None)


def _run_rollback_artifact_cleanups(session: Session) -> None:
    info = getattr(session, "info", None)
    if not isinstance(info, dict):
        return
    cleanups = info.pop(_ROLLBACK_ARTIFACT_PATHS, set())
    for root_raw, target_raw in cleanups:
        root = Path(root_raw).resolve()
        target = Path(target_raw).resolve()
        if not target.is_relative_to(root) or not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)


def _engine_kwargs(database_url: str) -> dict:
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    if database_url.startswith("sqlite:///"):
        return {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": True,
        }
    return {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        future=True,
        **_engine_kwargs(settings.database_url),
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.root_dir / "alembic.ini"))
    config.set_main_option("script_location", str(settings.root_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def init_db() -> None:
    config = _alembic_config()
    inspector = inspect(get_engine())
    has_version_table = inspector.has_table("alembic_version")
    if not has_version_table:
        managed_tables = {table.name for table in Base.metadata.sorted_tables}
        existing_tables = {
            name for name in inspector.get_table_names() if name != "sqlite_sequence"
        }
        if existing_tables.intersection(managed_tables):
            raise RuntimeError(
                "refusing to auto-upgrade an unversioned private-first database; "
                "recreate the database or stamp it with Alembic before booting the app"
            )
    command.upgrade(config, "head")


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
        _clear_rollback_artifact_cleanups(session)
    except Exception:
        session.rollback()
        _run_rollback_artifact_cleanups(session)
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
        _clear_rollback_artifact_cleanups(session)
    except Exception:
        session.rollback()
        _run_rollback_artifact_cleanups(session)
        raise
    finally:
        session.close()
