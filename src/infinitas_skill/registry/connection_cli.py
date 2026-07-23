from __future__ import annotations

import argparse
import os


def configure_registry_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("INFINITAS_REGISTRY_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Hosted registry API base URL",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("INFINITAS_REGISTRY_API_TOKEN", ""),
        help="Bearer token for hosted registry API",
    )


__all__ = ["configure_registry_connection_args"]
