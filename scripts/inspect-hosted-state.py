#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from server.models import Job, Submission


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Inspect hosted registry job and submission state')
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--limit', type=int, default=5, help='Number of recent rows to include in summaries')
    parser.add_argument('--max-queued-jobs', type=int, default=None, help='Alert when queued job count exceeds this threshold')
    parser.add_argument('--max-running-jobs', type=int, default=None, help='Alert when running job count exceeds this threshold')
    parser.add_argument('--max-failed-jobs', type=int, default=None, help='Alert when failed job count exceeds this threshold')
    parser.add_argument('--max-warning-jobs', type=int, default=None, help='Alert when jobs with WARNING log entries exceed this threshold')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser.parse_args()


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith('sqlite:///'):
        fail(f'unsupported database_url for phase 1 ops inspection: {database_url}')
    return Path(database_url.removeprefix('sqlite:///'))


def verify_sqlite(db_path: Path):
    if not db_path.exists():
        fail(f'sqlite database path does not exist: {db_path}')
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('select 1').fetchone()
    except sqlite3.Error as exc:
        fail(f'sqlite inspection failed for {db_path}: {exc}')
    finally:
        if 'conn' in locals():
            conn.close()


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace('+00:00', 'Z')


def summarize_counts(session: Session, model, label: str) -> dict:
    total = session.scalar(select(func.count()).select_from(model)) or 0
    by_status = {}
    for status, count in session.execute(select(model.status, func.count()).group_by(model.status)):
        by_status[status] = count
    return {'label': label, 'total': total, 'by_status': by_status}


def summarize_jobs(session: Session, limit: int) -> dict:
    counts = summarize_counts(session, Job, 'jobs')
    failed_rows = (
        session.query(Job)
        .filter(Job.status == 'failed')
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(limit)
        .all()
    )
    active_rows = (
        session.query(Job)
        .filter(Job.status.in_(['queued', 'running']))
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(limit)
        .all()
    )
    warning_rows = (
        session.query(Job)
        .filter(Job.log.contains('WARNING:'))
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(limit)
        .all()
    )
    return {
        'total': counts['total'],
        'by_status': counts['by_status'],
        'warning_count': session.scalar(select(func.count()).select_from(Job).where(Job.log.contains('WARNING:'))) or 0,
        'recent_failed': [
            {
                'id': row.id,
                'kind': row.kind,
                'submission_id': row.submission_id,
                'updated_at': _iso(row.updated_at),
                'error_message': row.error_message or '',
            }
            for row in failed_rows
        ],
        'recent_active': [
            {
                'id': row.id,
                'kind': row.kind,
                'status': row.status,
                'submission_id': row.submission_id,
                'updated_at': _iso(row.updated_at),
            }
            for row in active_rows
        ],
        'recent_warnings': [
            {
                'id': row.id,
                'kind': row.kind,
                'status': row.status,
                'submission_id': row.submission_id,
                'updated_at': _iso(row.updated_at),
                'warning_excerpt': next(
                    (
                        line.strip()
                        for line in (row.log or '').splitlines()
                        if 'WARNING:' in line
                    ),
                    '',
                ),
            }
            for row in warning_rows
        ],
    }


def summarize_submissions(session: Session, limit: int) -> dict:
    counts = summarize_counts(session, Submission, 'submissions')
    recent_rows = session.query(Submission).order_by(Submission.updated_at.desc(), Submission.id.desc()).limit(limit).all()
    return {
        'total': counts['total'],
        'by_status': counts['by_status'],
        'recent': [
            {
                'id': row.id,
                'skill_name': row.skill_name,
                'publisher': row.publisher,
                'status': row.status,
                'updated_at': _iso(row.updated_at),
            }
            for row in recent_rows
        ],
    }


def build_alerts(summary: dict, args: argparse.Namespace) -> list[dict]:
    alerts = []
    checks = [
        ('queued_jobs', summary['jobs']['by_status'].get('queued', 0), args.max_queued_jobs),
        ('running_jobs', summary['jobs']['by_status'].get('running', 0), args.max_running_jobs),
        ('failed_jobs', summary['jobs']['by_status'].get('failed', 0), args.max_failed_jobs),
        ('warning_jobs', summary['jobs'].get('warning_count', 0), args.max_warning_jobs),
    ]
    for kind, actual, threshold in checks:
        if threshold is None:
            continue
        if actual > threshold:
            alerts.append(
                {
                    'kind': kind,
                    'actual': actual,
                    'threshold': threshold,
                    'message': f'{kind} count {actual} exceeds threshold {threshold}',
                }
            )
    return alerts


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    jobs = summary['jobs']
    submissions = summary['submissions']
    prefix = 'OK' if summary.get('ok') else 'ALERT'
    print(
        f"{prefix}: jobs total={jobs['total']} queued={jobs['by_status'].get('queued', 0)} "
        f"failed={jobs['by_status'].get('failed', 0)} warnings={jobs.get('warning_count', 0)}"
    )
    print(f"{prefix}: submissions total={submissions['total']} statuses={json.dumps(submissions['by_status'], ensure_ascii=False, sort_keys=True)}")
    for item in jobs['recent_failed']:
        print(f"FAILED: job#{item['id']} kind={item['kind']} submission={item['submission_id']} error={item['error_message']}")
    for item in jobs.get('recent_warnings') or []:
        print(f"WARNED: job#{item['id']} kind={item['kind']} status={item['status']} warning={item['warning_excerpt']}")
    for alert in summary.get('alerts') or []:
        print(f"ALERT: {alert['message']}")


def main():
    args = parse_args()
    db_path = sqlite_path_from_url(args.database_url)
    verify_sqlite(db_path)

    engine = create_engine(args.database_url, future=True, connect_args={'check_same_thread': False})
    with Session(engine) as session:
        summary = {
            'database': {
                'kind': 'sqlite',
                'path': str(db_path),
            },
            'jobs': summarize_jobs(session, limit=max(args.limit, 1)),
            'submissions': summarize_submissions(session, limit=max(args.limit, 1)),
        }
    alerts = build_alerts(summary, args)
    summary['alerts'] = alerts
    summary['ok'] = not alerts
    emit(summary, as_json=args.json)
    raise SystemExit(2 if alerts else 0)


if __name__ == '__main__':
    main()
