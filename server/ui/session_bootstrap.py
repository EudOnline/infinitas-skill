from __future__ import annotations

from typing import Any

from server.ui.auth_state import hydrate_auth_state


def build_session_bootstrap(
    session_ui: dict[str, Any] | None,
    session_user: Any | None,
) -> dict[str, Any]:
    return hydrate_auth_state(session_ui, session_user)


__all__ = ["build_session_bootstrap"]
