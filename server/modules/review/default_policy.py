from __future__ import annotations

DEFAULT_POLICY_NAME = "private-first-default"
DEFAULT_POLICY_VERSION = "1"
DEFAULT_POLICY_RULES = {
    "public": "blocking",
    "grant": {
        "none": "none",
        "advisory": "advisory",
        "blocking": "blocking",
    },
    "private": "none",
    "authenticated": "none",
}
