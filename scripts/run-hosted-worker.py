#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_worker_parser, run_server_worker


def main(argv=None) -> int:
    parser = build_server_worker_parser(prog='run-hosted-worker.py')
    args = parser.parse_args(argv)
    return run_server_worker(
        poll_interval=args.poll_interval,
        once=args.once,
        limit=args.limit,
    )


if __name__ == '__main__':
    raise SystemExit(main())
