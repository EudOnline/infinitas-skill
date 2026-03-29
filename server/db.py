from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from server.models import Base, User
from server.settings import get_settings


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite:///"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True, **_engine_kwargs(settings.database_url))


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.root_dir / "alembic.ini"))
    config.set_main_option("script_location", str(settings.root_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def init_db():
    config = _alembic_config()
    inspector = inspect(get_engine())
    has_version_table = inspector.has_table("alembic_version")
    if not has_version_table:
        managed_tables = {table.name for table in Base.metadata.sorted_tables}
        existing_tables = {name for name in inspector.get_table_names() if name != "sqlite_sequence"}
        if existing_tables.intersection(managed_tables):
            raise RuntimeError(
                "refusing to auto-upgrade an unversioned private-first database; "
                "recreate the database or stamp it with Alembic before booting the app"
            )
    command.upgrade(config, "head")


def seed_bootstrap_users():
    from server.modules.access.service import ensure_personal_credential_for_user, ensure_user_principal

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        existing = {user.username: user for user in session.query(User).all()}
        for item in settings.bootstrap_users:
            user = existing.get(item["username"])
            if user is None:
                user = User(
                    username=item["username"],
                    display_name=item["display_name"],
                    role=item["role"],
                    token=None,
                )
                session.add(user)
                existing[user.username] = user
            if user.display_name != item["display_name"] or user.role != item["role"]:
                user.display_name = item["display_name"]
                user.role = item["role"]
            if user.token is not None:
                user.token = None
            principal = ensure_user_principal(session, user)
            ensure_personal_credential_for_user(
                session,
                user=user,
                principal=principal,
                raw_token=item["token"],
            )
        if settings.bootstrap_users:
            session.commit()


def ensure_database_ready():
    init_db()
    seed_bootstrap_users()


def get_db():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
