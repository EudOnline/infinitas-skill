from __future__ import annotations


def validate_ai_index_payload(payload: dict) -> list:
    from .ai_index_payload_validation import validate_ai_index_payload

    return validate_ai_index_payload(payload)


__all__ = ["validate_ai_index_payload"]
