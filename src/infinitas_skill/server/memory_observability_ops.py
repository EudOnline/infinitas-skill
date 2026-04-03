from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.server.memory_observability import summarize_memory_observability
from infinitas_skill.server.repo_checks import require_sqlite_db


def server_engine_kwargs(database_url: str) -> dict[str, Any]:
    if database_url.startswith('sqlite:///'):
        return {'connect_args': {'check_same_thread': False}}
    return {}


def configure_server_memory_observability_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        '--database-url',
        required=True,
        help='Database URL, currently sqlite:///... only',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Number of recent audit rows per memory stream to inspect',
    )
    parser.add_argument(
        '--job-limit',
        type=int,
        default=10,
        help='Number of recent memory curation jobs to inspect',
    )
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def build_server_memory_observability_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Inspect hosted registry memory operations health',
        prog=prog,
    )
    return configure_server_memory_observability_parser(parser)


def run_server_memory_observability(
    *,
    database_url: str,
    limit: int,
    job_limit: int,
    as_json: bool = False,
) -> int:
    require_sqlite_db(database_url)
    engine = create_engine(database_url, future=True, **server_engine_kwargs(database_url))
    try:
        with Session(engine) as session:
            summary = summarize_memory_observability(session, limit=limit, job_limit=job_limit)
    finally:
        engine.dispose()

    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            "OK: memory observability "
            f"writeback_statuses={summary['writeback']['writeback_status_counts']} "
            f"curation_statuses={summary['curation']['status_counts']} "
            f"job_statuses={summary['jobs']['status_counts']}"
        )
    return 0


__all__ = [
    'build_server_memory_observability_parser',
    'configure_server_memory_observability_parser',
    'run_server_memory_observability',
]
