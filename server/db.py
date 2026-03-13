from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from server.models import Base, User
from server.settings import get_settings


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith('sqlite:///'):
        return {'connect_args': {'check_same_thread': False}}
    return {}


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    if settings.database_url.startswith('sqlite:///'):
        db_path = Path(settings.database_url.removeprefix('sqlite:///'))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True, **_engine_kwargs(settings.database_url))


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def init_db():
    Base.metadata.create_all(bind=get_engine())


def seed_bootstrap_users():
    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        existing = {user.username: user for user in session.query(User).all()}
        changed = False
        for item in settings.bootstrap_users:
            user = existing.get(item['username'])
            if user is None:
                session.add(
                    User(
                        username=item['username'],
                        display_name=item['display_name'],
                        role=item['role'],
                        token=item['token'],
                    )
                )
                changed = True
                continue
            if user.display_name != item['display_name'] or user.role != item['role'] or user.token != item['token']:
                user.display_name = item['display_name']
                user.role = item['role']
                user.token = item['token']
                changed = True
        if changed:
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
