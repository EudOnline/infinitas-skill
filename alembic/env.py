from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from server.models import Base
from server.settings import get_settings


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option('sqlalchemy.url', settings.database_url)

target_metadata = Base.metadata


def _ensure_sqlite_path(database_url: str) -> None:
    if not database_url.startswith('sqlite:///'):
        return
    db_path = Path(database_url.removeprefix('sqlite:///'))
    db_path.parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    url = config.get_main_option('sqlalchemy.url')
    _ensure_sqlite_path(url)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _ensure_sqlite_path(config.get_main_option('sqlalchemy.url'))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
