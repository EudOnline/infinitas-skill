#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.server.ops import build_server_render_systemd_parser, run_server_render_systemd


def main(argv=None):
    parser = build_server_render_systemd_parser(prog='render-hosted-systemd.py')
    args = parser.parse_args(argv)
    return run_server_render_systemd(args)


if __name__ == '__main__':
    raise SystemExit(main())
