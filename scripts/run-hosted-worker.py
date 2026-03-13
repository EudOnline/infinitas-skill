#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

from server.db import ensure_database_ready
from server.worker import run_worker_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the hosted registry worker loop')
    parser.add_argument('--poll-interval', type=float, default=5.0, help='Seconds to wait between empty queue polls')
    parser.add_argument('--once', action='store_true', help='Drain the queue once and exit')
    parser.add_argument('--limit', type=int, default=None, help='Maximum jobs to process per loop iteration')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_database_ready()
    if args.once:
        processed = run_worker_loop(limit=args.limit)
        print(f'processed {processed} job(s) in once mode')
        return 0

    try:
        while True:
            processed = run_worker_loop(limit=args.limit)
            print(f'processed {processed} job(s)')
            if processed == 0:
                time.sleep(max(args.poll_interval, 0.1))
    except KeyboardInterrupt:
        print('worker loop interrupted; exiting cleanly')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
