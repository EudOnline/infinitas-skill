from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from server.models import User
from server.settings import get_settings

BOOTSTRAP_REVISION = '20260329_0001'
RELEASE_GRAPH_REVISION = '20260329_0002'
COMPATIBILITY_TABLE_COLUMNS = {
    'users': {
        'id': ('INTEGER', False, True),
        'username': ('VARCHAR(100)', False, False),
        'display_name': ('VARCHAR(200)', False, False),
        'role': ('VARCHAR(32)', False, False),
        'token': ('VARCHAR(255)', False, False),
        'light_bg_id': ('VARCHAR(64)', True, False),
        'dark_bg_id': ('VARCHAR(64)', True, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'submissions': {
        'id': ('INTEGER', False, True),
        'skill_name': ('VARCHAR(200)', False, False),
        'publisher': ('VARCHAR(200)', False, False),
        'status': ('VARCHAR(64)', False, False),
        'payload_json': ('TEXT', False, False),
        'payload_summary': ('TEXT', False, False),
        'status_log_json': ('TEXT', False, False),
        'created_by_user_id': ('INTEGER', True, False),
        'updated_by_user_id': ('INTEGER', True, False),
        'review_requested_at': ('DATETIME', True, False),
        'approved_at': ('DATETIME', True, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'reviews': {
        'id': ('INTEGER', False, True),
        'submission_id': ('INTEGER', False, False),
        'status': ('VARCHAR(64)', False, False),
        'note': ('TEXT', False, False),
        'requested_by_user_id': ('INTEGER', True, False),
        'reviewed_by_user_id': ('INTEGER', True, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'jobs': {
        'id': ('INTEGER', False, True),
        'kind': ('VARCHAR(100)', False, False),
        'status': ('VARCHAR(64)', False, False),
        'payload_json': ('TEXT', False, False),
        'submission_id': ('INTEGER', True, False),
        'requested_by_user_id': ('INTEGER', True, False),
        'note': ('TEXT', False, False),
        'log': ('TEXT', False, False),
        'started_at': ('DATETIME', True, False),
        'finished_at': ('DATETIME', True, False),
        'error_message': ('TEXT', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
}
RELEASE_GRAPH_TABLE_COLUMNS = {
    'namespaces': {
        'id': ('INTEGER', False, True),
        'slug': ('VARCHAR(200)', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'skills': {
        'id': ('INTEGER', False, True),
        'namespace_id': ('INTEGER', False, False),
        'slug': ('VARCHAR(200)', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'skill_drafts': {
        'id': ('INTEGER', False, True),
        'skill_id': ('INTEGER', False, False),
        'state': ('VARCHAR(64)', False, False),
        'payload_json': ('TEXT', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'skill_versions': {
        'id': ('INTEGER', False, True),
        'skill_id': ('INTEGER', False, False),
        'version': ('VARCHAR(64)', False, False),
        'payload_json': ('TEXT', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'releases': {
        'id': ('INTEGER', False, True),
        'skill_version_id': ('INTEGER', False, False),
        'state': ('VARCHAR(64)', False, False),
        'created_at': ('DATETIME', False, False),
        'updated_at': ('DATETIME', False, False),
    },
    'artifacts': {
        'id': ('INTEGER', False, True),
        'release_id': ('INTEGER', False, False),
        'kind': ('VARCHAR(64)', False, False),
        'digest': ('VARCHAR(255)', False, False),
        'path': ('TEXT', False, False),
        'created_at': ('DATETIME', False, False),
    },
}
COMPATIBILITY_TABLE_INDEXES = {
    'users': frozenset(
        {
            (('token',), True),
            (('username',), True),
        }
    ),
    'submissions': frozenset(
        {
            (('skill_name',), False),
            (('status',), False),
        }
    ),
    'reviews': frozenset(
        {
            (('status',), False),
            (('submission_id',), False),
        }
    ),
    'jobs': frozenset(
        {
            (('kind',), False),
            (('status',), False),
            (('submission_id',), False),
        }
    ),
}
RELEASE_GRAPH_TABLE_INDEXES = {
    'namespaces': frozenset(
        {
            (('slug',), True),
        }
    ),
    'skills': frozenset(
        {
            (('namespace_id', 'slug'), True),
        }
    ),
    'skill_drafts': frozenset(
        {
            (('skill_id', 'state'), False),
        }
    ),
    'skill_versions': frozenset(
        {
            (('skill_id', 'version'), True),
        }
    ),
    'releases': frozenset(
        {
            (('skill_version_id', 'state'), False),
        }
    ),
    'artifacts': frozenset(
        {
            (('release_id', 'kind', 'digest'), True),
        }
    ),
}
COMPATIBILITY_TABLE_FOREIGN_KEYS = {
    'users': frozenset(),
    'submissions': frozenset(
        {
            (('created_by_user_id',), 'users', ('id',)),
            (('updated_by_user_id',), 'users', ('id',)),
        }
    ),
    'reviews': frozenset(
        {
            (('submission_id',), 'submissions', ('id',)),
            (('requested_by_user_id',), 'users', ('id',)),
            (('reviewed_by_user_id',), 'users', ('id',)),
        }
    ),
    'jobs': frozenset(
        {
            (('submission_id',), 'submissions', ('id',)),
            (('requested_by_user_id',), 'users', ('id',)),
        }
    ),
}
RELEASE_GRAPH_TABLE_FOREIGN_KEYS = {
    'namespaces': frozenset(),
    'skills': frozenset(
        {
            (('namespace_id',), 'namespaces', ('id',)),
        }
    ),
    'skill_drafts': frozenset(
        {
            (('skill_id',), 'skills', ('id',)),
        }
    ),
    'skill_versions': frozenset(
        {
            (('skill_id',), 'skills', ('id',)),
        }
    ),
    'releases': frozenset(
        {
            (('skill_version_id',), 'skill_versions', ('id',)),
        }
    ),
    'artifacts': frozenset(
        {
            (('release_id',), 'releases', ('id',)),
        }
    ),
}


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


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.root_dir / 'alembic.ini'))
    config.set_main_option('script_location', str(settings.root_dir / 'alembic'))
    config.set_main_option('sqlalchemy.url', settings.database_url)
    return config


def _tables_match_signature(inspector, expected_columns_map, expected_indexes_map, expected_foreign_keys_map) -> bool:
    for table_name, expected_columns in expected_columns_map.items():
        actual_columns = {
            column['name']: (
                str(column['type']),
                bool(column['nullable']),
                bool(column.get('primary_key')),
            )
            for column in inspector.get_columns(table_name)
        }
        if actual_columns != expected_columns:
            return False
        actual_indexes = {
            (
                tuple(index['column_names']),
                bool(index.get('unique', False)),
            )
            for index in inspector.get_indexes(table_name)
        }
        if actual_indexes != expected_indexes_map[table_name]:
            return False
        actual_foreign_keys = {
            (
                tuple(foreign_key['constrained_columns']),
                foreign_key['referred_table'],
                tuple(foreign_key['referred_columns']),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        if actual_foreign_keys != expected_foreign_keys_map[table_name]:
            return False
    return True


def init_db():
    config = _alembic_config()
    inspector = inspect(get_engine())
    has_version_table = inspector.has_table('alembic_version')
    existing_compatibility_tables = [name for name in COMPATIBILITY_TABLE_COLUMNS if inspector.has_table(name)]
    has_compatibility_tables = len(existing_compatibility_tables) == len(COMPATIBILITY_TABLE_COLUMNS)
    existing_release_graph_tables = [name for name in RELEASE_GRAPH_TABLE_COLUMNS if inspector.has_table(name)]
    has_release_graph_tables = len(existing_release_graph_tables) == len(RELEASE_GRAPH_TABLE_COLUMNS)
    if not has_version_table:
        if has_release_graph_tables:
            if not has_compatibility_tables:
                raise RuntimeError(
                    f'refusing to auto-stamp unversioned database with release graph tables; missing compatibility tables for head revision {RELEASE_GRAPH_REVISION}'
                )
            if not _tables_match_signature(
                inspector,
                COMPATIBILITY_TABLE_COLUMNS,
                COMPATIBILITY_TABLE_INDEXES,
                COMPATIBILITY_TABLE_FOREIGN_KEYS,
            ) or not _tables_match_signature(
                inspector,
                RELEASE_GRAPH_TABLE_COLUMNS,
                RELEASE_GRAPH_TABLE_INDEXES,
                RELEASE_GRAPH_TABLE_FOREIGN_KEYS,
            ):
                raise RuntimeError(
                    f'refusing to auto-stamp unversioned private registry database; managed tables do not match head revision {RELEASE_GRAPH_REVISION}'
                )
            command.stamp(config, RELEASE_GRAPH_REVISION)
        elif has_compatibility_tables:
            if not _tables_match_signature(
                inspector,
                COMPATIBILITY_TABLE_COLUMNS,
                COMPATIBILITY_TABLE_INDEXES,
                COMPATIBILITY_TABLE_FOREIGN_KEYS,
            ):
                raise RuntimeError(
                    f'refusing to auto-stamp unversioned legacy database; compatibility tables do not match bootstrap revision {BOOTSTRAP_REVISION}'
                )
            command.stamp(config, BOOTSTRAP_REVISION)
        elif existing_compatibility_tables or existing_release_graph_tables:
            raise RuntimeError(
                f'refusing to auto-stamp partially initialized database; managed tables do not match bootstrap revision {BOOTSTRAP_REVISION} or head revision {RELEASE_GRAPH_REVISION}'
            )
    command.upgrade(config, 'head')


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
