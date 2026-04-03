from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.server.memory_baselines import summarize_memory_baselines
from infinitas_skill.server.repo_checks import require_sqlite_db


def server_engine_kwargs(database_url: str) -> dict[str, Any]:
    if database_url.startswith('sqlite:///'):
        return {'connect_args': {'check_same_thread': False}}
    return {}


def configure_server_memory_baselines_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        '--database-url',
        required=True,
        help='Database URL, currently sqlite:///... only',
    )
    parser.add_argument(
        '--window-hours',
        type=int,
        default=24,
        help='Hours per rolling baseline window',
    )
    parser.add_argument(
        '--now',
        default='',
        help='Optional ISO timestamp used as the rolling baseline anchor',
    )
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def build_server_memory_baselines_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Inspect rolling memory baselines', prog=prog)
    return configure_server_memory_baselines_parser(parser)


def run_server_memory_baselines(
    *,
    database_url: str,
    window_hours: int,
    now: str = '',
    as_json: bool = False,
) -> int:
    require_sqlite_db(database_url)
    engine = create_engine(database_url, future=True, **server_engine_kwargs(database_url))
    try:
        with Session(engine) as session:
            summary = summarize_memory_baselines(
                session,
                now=now or None,
                window_hours=window_hours,
            )
    finally:
        engine.dispose()

    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            "OK: memory baselines "
            f"window_hours={summary['window_hours']} "
            f"writeback_recent={summary['writeback']['recent']['totals']['count']} "
            f"curation_recent={summary['curation']['recent']['totals']['count']} "
            f"jobs_recent={summary['jobs']['recent']['totals']['count']} "
            f"retrieval_recent={summary['retrieval']['recent']['totals']['count']}"
        )
    return 0


__all__ = [
    'build_server_memory_baselines_parser',
    'configure_server_memory_baselines_parser',
    'run_server_memory_baselines',
]
