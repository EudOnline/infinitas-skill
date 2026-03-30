#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_healthcheck_parser, run_server_healthcheck


def main(argv=None):
    parser = build_server_healthcheck_parser(prog='server-healthcheck.py')
    args = parser.parse_args(argv)
    return run_server_healthcheck(
        api_url=args.api_url,
        repo_path=args.repo_path,
        artifact_path=args.artifact_path,
        database_url=args.database_url,
        token=args.token,
        as_json=args.json,
    )


if __name__ == '__main__':
    raise SystemExit(main())
