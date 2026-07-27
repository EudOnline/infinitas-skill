from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import NoReturn

from infinitas_skill.registry.publish import HostedPublishError


def wrap_hosted_handler(
    func: Callable[[argparse.Namespace], object],
    fail: Callable[[str], NoReturn],
) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        try:
            result = func(args)
        except HostedPublishError as exc:
            fail(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return handler


__all__ = ["wrap_hosted_handler"]
