#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_backup_parser, run_server_backup


def main(argv=None):
    parser = build_server_backup_parser(prog='backup-hosted-registry.py')
    args = parser.parse_args(argv)
    return run_server_backup(
        repo_path=args.repo_path,
        database_url=args.database_url,
        artifact_path=args.artifact_path,
        output_dir=args.output_dir,
        label=args.label,
        as_json=args.json,
    )


if __name__ == '__main__':
    raise SystemExit(main())
