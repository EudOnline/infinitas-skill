from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import NoReturn

import httpx

from infinitas_skill.registry.publish import HostedPublishError


def format_http_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip() or "request failed"
    else:
        detail = body.get("detail", body) if isinstance(body, dict) else body
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
    return f"registry returned HTTP {response.status_code}: {detail}"


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


__all__ = ["format_http_error", "wrap_hosted_handler"]
