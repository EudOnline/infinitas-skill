from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.memory import build_memory_provider
from infinitas_skill.server.memory_curation import (
    execute_memory_curation,
    summarize_memory_curation_plan,
)
from infinitas_skill.server.memory_curation_queue import (
    build_memory_curation_job_summary,
    enqueue_memory_curation_job,
)
from infinitas_skill.server.repo_checks import require_sqlite_db


def server_engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith('sqlite:///'):
        return {'connect_args': {'check_same_thread': False}}
    return {}


def configure_server_memory_curation_parser(
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
        default=50,
        help='Number of recent memory writeback audit events to inspect',
    )
    parser.add_argument(
        '--action',
        choices=('plan', 'archive', 'prune'),
        default='plan',
        help='Curation mode: read-only planning, local archive audit, or guarded provider prune',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Execute the selected action; omitted means dry-run even for archive/prune',
    )
    parser.add_argument(
        '--max-actions',
        type=int,
        default=20,
        help='Maximum actionable candidates to archive or prune in one run',
    )
    parser.add_argument(
        '--actor-ref',
        default='system:memory-curation',
        help='Actor reference recorded on memory curation audit events',
    )
    parser.add_argument(
        '--enqueue',
        action='store_true',
        help='Queue the curation action for the hosted worker instead of running immediately',
    )
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def build_server_memory_curation_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Inspect hosted registry memory curation candidates',
        prog=prog,
    )
    return configure_server_memory_curation_parser(parser)


def run_server_memory_curation(
    *,
    database_url: str,
    limit: int,
    action: str = 'plan',
    apply: bool = False,
    max_actions: int = 20,
    actor_ref: str = 'system:memory-curation',
    enqueue: bool = False,
    as_json: bool = False,
) -> int:
    require_sqlite_db(database_url)
    engine = create_engine(database_url, future=True, **server_engine_kwargs(database_url))
    try:
        with Session(engine) as session:
            if enqueue:
                job = enqueue_memory_curation_job(
                    session,
                    action=action,
                    apply=apply,
                    limit=limit,
                    max_actions=max_actions,
                    actor_ref=actor_ref,
                )
                summary = {
                    'ok': True,
                    'queued': True,
                    'job': build_memory_curation_job_summary(job),
                }
            elif action == 'plan':
                summary = summarize_memory_curation_plan(session, limit=limit)
            else:
                provider = build_memory_provider() if action == 'prune' and apply else None
                summary = execute_memory_curation(
                    session,
                    action=action,
                    apply=apply,
                    provider=provider,
                    limit=limit,
                    max_actions=max_actions,
                    actor_ref=actor_ref,
                )
                if summary['apply']:
                    session.commit()
    finally:
        engine.dispose()

    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if enqueue:
        print(
            "OK: queued memory curation "
            f"id={summary['job']['id']} action={summary['job']['payload'].get('action')} "
            f"apply={summary['job']['payload'].get('apply')}"
        )
        return 0
    print(
        "OK: memory curation "
        f"action={summary['action']} apply={summary['apply']} "
        f"duplicate_groups={summary['candidate_counts']['duplicate_groups']} "
        f"expired_by_policy={summary['candidate_counts']['expired_by_policy']} "
        f"selected={summary['execution']['selected_candidates']} "
        f"archived={summary['execution']['archived']} "
        f"pruned={summary['execution']['pruned']} "
        f"skipped={summary['execution']['skipped']} "
        f"failed={summary['execution']['failed']}"
    )
    return 0


__all__ = [
    'build_server_memory_curation_parser',
    'configure_server_memory_curation_parser',
    'run_server_memory_curation',
]
