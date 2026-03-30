#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_prune_backups_parser, run_server_prune_backups


def main(argv=None):
    parser = build_server_prune_backups_parser(prog='prune-hosted-backups.py')
    args = parser.parse_args(argv)
    return run_server_prune_backups(
        backup_root=args.backup_root,
        keep_last=args.keep_last,
        as_json=args.json,
    )


if __name__ == '__main__':
    raise SystemExit(main())
