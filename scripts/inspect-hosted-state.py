#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_inspect_state_parser, run_server_inspect_state


def main(argv=None) -> int:
    parser = build_server_inspect_state_parser(prog='inspect-hosted-state.py')
    args = parser.parse_args(argv)
    return run_server_inspect_state(
        database_url=args.database_url,
        limit=args.limit,
        max_queued_jobs=args.max_queued_jobs,
        max_running_jobs=args.max_running_jobs,
        max_failed_jobs=args.max_failed_jobs,
        max_warning_jobs=args.max_warning_jobs,
        alert_webhook_url=args.alert_webhook_url,
        alert_fallback_file=args.alert_fallback_file,
        as_json=args.json,
    )


if __name__ == '__main__':
    raise SystemExit(main())
