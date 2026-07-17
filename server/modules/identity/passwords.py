from __future__ import annotations

import bcrypt


def validate_password_strength(plain: str) -> None:
    if len(plain) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(plain) > 128:
        raise ValueError("Password must be at most 128 characters")
    categories = sum(
        (
            any(character.islower() for character in plain),
            any(character.isupper() for character in plain),
            any(character.isdigit() for character in plain),
            any(not character.isalnum() for character in plain),
        )
    )
    if categories < 2:
        raise ValueError(
            "Password must contain at least 2 of: "
            "lowercase letters, uppercase letters, digits, special characters"
        )


def hash_password(plain: str) -> str:
    validate_password_strength(plain)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def hash_share_password(plain: str) -> str:
    if not plain or len(plain) < 4:
        raise ValueError("Share password must be at least 4 characters")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
