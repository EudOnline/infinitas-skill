from __future__ import annotations

import os


_SKIP_TEST_FLAGS = (
    "INFINITAS_SKIP_RELEASE_TESTS",
    "INFINITAS_SKIP_ATTESTATION_TESTS",
    "INFINITAS_SKIP_DISTRIBUTION_TESTS",
    "INFINITAS_SKIP_BOOTSTRAP_TESTS",
    "INFINITAS_SKIP_AI_WRAPPER_TESTS",
    "INFINITAS_SKIP_COMPAT_PIPELINE_TESTS",
    "INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS",
)


def make_test_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in _SKIP_TEST_FLAGS:
        env[key] = "1"
    if extra:
        env.update(extra)
    return env
