from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER_ENV = "development"
DEFAULT_SECRET_KEY = "dev-only-insecure-key"  # noqa: S105
DEFAULT_ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "::1"]
MIN_SECRET_KEY_LENGTH = 32  # Minimum secure key length in bytes


def validate_secret_key_strength(secret_key: str, environment: str) -> None:
    """Validate secret key meets security requirements.

    Args:
        secret_key: The secret key to validate
        environment: Current server environment

    Raises:
        RuntimeError: If the key doesn't meet security requirements
    """
    if not secret_key:
        raise RuntimeError("INFINITAS_SERVER_SECRET_KEY cannot be empty")

    # In test mode, allow shorter keys for convenience
    if environment == "test":
        if len(secret_key) < 8:
            raise RuntimeError(
                f"INFINITAS_SERVER_SECRET_KEY must be at least 8 characters in test mode. "
                f"Current length: {len(secret_key)}."
            )
        return

    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"INFINITAS_SERVER_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters. "
            f"Current length: {len(secret_key)}. "
            f'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )

    # Check for obviously weak keys in production
    if environment == "production":
        weak_patterns = [
            DEFAULT_SECRET_KEY,
            "secret",
            "password",
            "key",
            "test",
            "dev",
            "123456",
            "password123",
        ]
        lower_key = secret_key.lower()
        for pattern in weak_patterns:
            if pattern in lower_key:
                raise RuntimeError(
                    f'INFINITAS_SERVER_SECRET_KEY contains weak pattern "{pattern}". '
                    f'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )

        # Check for repeated characters (indicates poor randomness)
        if len(set(secret_key)) < len(secret_key) * 0.5:
            raise RuntimeError(
                "INFINITAS_SERVER_SECRET_KEY appears to have low entropy. "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )


DEFAULT_BOOTSTRAP_USERS = [
    {
        "username": "maintainer",
        "display_name": "Default Maintainer",
        "role": "maintainer",
    },
    {
        "username": "contributor",
        "display_name": "Default Contributor",
        "role": "contributor",
    },
]


@dataclass(frozen=True)
class Settings:
    app_name: str
    root_dir: Path
    environment: str
    database_url: str
    secret_key: str
    allowed_hosts: list[str]
    template_dir: Path
    bootstrap_users: list[dict]
    repo_path: Path
    artifact_path: Path
    registry_read_tokens: list[str]
    trusted_proxies: list[str]


def _normalize_bootstrap_users(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        return []

    normalized = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        display_name = str(item.get("display_name") or username).strip()
        role = str(item.get("role") or "contributor").strip() or "contributor"
        token = str(item.get("token") or "").strip()
        password = str(item.get("password") or "").strip()
        if not username:
            continue
        normalized.append(
            {
                "username": username,
                "display_name": display_name or username,
                "role": role,
                "token": token,
                "password": password,
            }
        )
    return normalized


def _normalize_environment(raw: str | None) -> str:
    environment = str(raw or DEFAULT_SERVER_ENV).strip().lower() or DEFAULT_SERVER_ENV
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("INFINITAS_SERVER_ENV must be one of development, test, or production")
    return environment


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_bootstrap_payload(raw: str | None, *, allow_default_fixture: bool) -> object:
    if not raw:
        return list(DEFAULT_BOOTSTRAP_USERS) if allow_default_fixture else None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return list(DEFAULT_BOOTSTRAP_USERS) if allow_default_fixture else None


def _normalize_string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    normalized = []
    for item in payload:
        value = str(item or "").strip()
        if value:
            normalized.append(value)
    return normalized


def _load_string_list_env(name: str, *, strict: bool) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if strict:
            raise RuntimeError(f"{name} must be a JSON array of strings") from exc
        return []
    if not isinstance(payload, list):
        if strict:
            raise RuntimeError(f"{name} must be a JSON array of strings")
        return []
    return _normalize_string_list(payload)


def _load_allowed_hosts(environment: str) -> list[str]:
    hosts = _load_string_list_env(
        "INFINITAS_SERVER_ALLOWED_HOSTS",
        strict=environment == "production",
    )
    normalized = list(dict.fromkeys(hosts))
    if normalized:
        return normalized
    if environment == "production":
        raise RuntimeError(
            "INFINITAS_SERVER_ALLOWED_HOSTS must be set to a non-empty JSON array "
            "when INFINITAS_SERVER_ENV=production"
        )
    return list(DEFAULT_ALLOWED_HOSTS)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = _normalize_environment(os.environ.get("INFINITAS_SERVER_ENV"))
    allow_insecure_defaults = environment in {"development", "test"} or _env_flag(
        "INFINITAS_SERVER_ALLOW_INSECURE_DEFAULTS"
    )

    secret_key = str(os.environ.get("INFINITAS_SERVER_SECRET_KEY") or "").strip()
    if not secret_key and allow_insecure_defaults:
        secret_key = DEFAULT_SECRET_KEY
    if not secret_key or secret_key == DEFAULT_SECRET_KEY:
        if not allow_insecure_defaults:
            raise RuntimeError(
                "INFINITAS_SERVER_SECRET_KEY must be set to a secure, non-default value "
                "when INFINITAS_SERVER_ENV=production. "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        secret_key = DEFAULT_SECRET_KEY
    else:
        # Validate secret key strength for non-default keys
        validate_secret_key_strength(secret_key, environment)
    allowed_hosts = _load_allowed_hosts(environment)

    bootstrap_raw = os.environ.get("INFINITAS_SERVER_BOOTSTRAP_USERS")
    bootstrap_payload = _load_bootstrap_payload(
        bootstrap_raw,
        allow_default_fixture=allow_insecure_defaults,
    )
    bootstrap_users = _normalize_bootstrap_users(bootstrap_payload)
    if not bootstrap_users:
        if not allow_insecure_defaults:
            raise RuntimeError(
                "INFINITAS_SERVER_BOOTSTRAP_USERS must be set to a non-empty JSON array "
                "when INFINITAS_SERVER_ENV=production"
            )
        bootstrap_users = _normalize_bootstrap_users(list(DEFAULT_BOOTSTRAP_USERS))

    default_db_path = ROOT / ".state" / "server.db"
    database_url = os.environ.get("INFINITAS_SERVER_DATABASE_URL") or f"sqlite:///{default_db_path}"
    repo_path = Path(os.environ.get("INFINITAS_SERVER_REPO_PATH") or ROOT).expanduser().resolve()
    artifact_path = (
        Path(os.environ.get("INFINITAS_SERVER_ARTIFACT_PATH") or (ROOT / ".state" / "artifacts"))
        .expanduser()
        .resolve()
    )
    registry_read_tokens = _load_string_list_env(
        "INFINITAS_REGISTRY_READ_TOKENS",
        strict=environment == "production",
    )
    trusted_proxies = _load_string_list_env(
        "INFINITAS_SERVER_TRUSTED_PROXIES",
        strict=False,
    )

    return Settings(
        app_name="infinitas-hosted-registry",
        root_dir=ROOT,
        environment=environment,
        database_url=database_url,
        secret_key=secret_key,
        allowed_hosts=allowed_hosts,
        template_dir=ROOT / "server" / "templates",
        bootstrap_users=bootstrap_users,
        repo_path=repo_path,
        artifact_path=artifact_path,
        registry_read_tokens=registry_read_tokens,
        trusted_proxies=trusted_proxies,
    )
