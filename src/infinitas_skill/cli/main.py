import argparse

from infinitas_skill.compatibility.checks import (
    COMPATIBILITY_PARSER_DESCRIPTION,
    COMPATIBILITY_TOP_LEVEL_HELP,
    configure_compatibility_cli,
)
from infinitas_skill.discovery.cli import (
    DISCOVERY_PARSER_DESCRIPTION,
    DISCOVERY_TOP_LEVEL_HELP,
    configure_discovery_parser,
)
from infinitas_skill.install.cli import configure_install_cli
from infinitas_skill.openclaw.cli import (
    OPENCLAW_PARSER_DESCRIPTION,
    OPENCLAW_TOP_LEVEL_HELP,
    configure_openclaw_parser,
)
from infinitas_skill.policy.cli import (
    POLICY_PARSER_DESCRIPTION,
    POLICY_TOP_LEVEL_HELP,
    configure_policy_parser,
)
from infinitas_skill.registry.cli import (
    REGISTRY_PARSER_DESCRIPTION,
    REGISTRY_TOP_LEVEL_HELP,
    configure_registry_parser,
)
from infinitas_skill.release.cli import (
    RELEASE_PARSER_DESCRIPTION,
    RELEASE_TOP_LEVEL_HELP,
    configure_release_parser,
)
from infinitas_skill.server.ops import (
    SERVER_PARSER_DESCRIPTION,
    SERVER_TOP_LEVEL_HELP,
    configure_server_parser,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="infinitas", description="infinitas project CLI")
    top = parser.add_subparsers(dest="command")

    compatibility = top.add_parser(
        "compatibility",
        help=COMPATIBILITY_TOP_LEVEL_HELP,
        description=COMPATIBILITY_PARSER_DESCRIPTION,
    )
    configure_compatibility_cli(compatibility)

    release = top.add_parser(
        "release",
        help=RELEASE_TOP_LEVEL_HELP,
        description=RELEASE_PARSER_DESCRIPTION,
    )
    configure_release_parser(release)

    install = top.add_parser("install", help="Install planning and workflow tools")
    configure_install_cli(install)

    discovery = top.add_parser(
        "discovery",
        help=DISCOVERY_TOP_LEVEL_HELP,
        description=DISCOVERY_PARSER_DESCRIPTION,
    )
    configure_discovery_parser(discovery)

    openclaw = top.add_parser(
        "openclaw",
        help=OPENCLAW_TOP_LEVEL_HELP,
        description=OPENCLAW_PARSER_DESCRIPTION,
    )
    configure_openclaw_parser(openclaw)

    registry = top.add_parser(
        "registry",
        help=REGISTRY_TOP_LEVEL_HELP,
        description=REGISTRY_PARSER_DESCRIPTION,
    )
    configure_registry_parser(registry)

    policy = top.add_parser(
        "policy",
        help=POLICY_TOP_LEVEL_HELP,
        description=POLICY_PARSER_DESCRIPTION,
    )
    configure_policy_parser(policy)

    server = top.add_parser(
        "server",
        help=SERVER_TOP_LEVEL_HELP,
        description=SERVER_PARSER_DESCRIPTION,
    )
    configure_server_parser(server)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
