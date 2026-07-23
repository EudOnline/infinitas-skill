from __future__ import annotations

import argparse

from infinitas_skill.registry.local_ops import run_registry_bootstrap


def configure_registry_bootstrap_command(
    subparsers: argparse._SubParsersAction,
) -> None:
    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="Configure a Hosted Registry and install its public trust policy",
    )
    bootstrap.add_argument("name", help="Registry source name in lowercase kebab-case")
    bootstrap.add_argument("base_url", help="Hosted catalog base URL")
    bootstrap.add_argument("--repo-root", default=".")
    bootstrap.add_argument(
        "--token-env",
        default="INFINITAS_REGISTRY_READ_TOKEN",
        help="Environment variable containing the Registry reader token",
    )
    bootstrap.add_argument("--set-default", action="store_true")
    bootstrap.add_argument(
        "--force-trust",
        action="store_true",
        help="Replace existing trust files when they differ",
    )
    bootstrap.add_argument("--json", action="store_true")
    bootstrap.set_defaults(_handler=run_registry_bootstrap)


__all__ = ["configure_registry_bootstrap_command"]
