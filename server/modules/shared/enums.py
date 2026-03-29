from __future__ import annotations

from enum import StrEnum


class ExposureMode(StrEnum):
    PRIVATE = 'private'
    GRANT = 'grant'
    PUBLIC = 'public'


class ReviewRequirement(StrEnum):
    NONE = 'none'
    BLOCKING = 'blocking'
