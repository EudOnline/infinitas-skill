#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.discovery.search import *  # noqa: E402,F401,F403
from infinitas_skill.discovery.inspect import *  # noqa: E402,F401,F403
