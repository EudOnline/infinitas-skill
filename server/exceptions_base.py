"""Base exception classes for the server.

These exceptions are imported by both the exception handlers (server/exceptions.py)
and the domain service modules.  Keeping them in a separate module avoids the
circular import chain that would otherwise occur between server/exceptions.py
(which imports UI modules) and the service layer.
"""

from __future__ import annotations


class NotFoundError(Exception):
    """Raised when a requested entity is not found."""

    pass


class ForbiddenError(Exception):
    """Raised when access to a resource is forbidden."""

    pass


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


class ConflictError(Exception):
    """Raised when a resource state conflict occurs."""

    pass
