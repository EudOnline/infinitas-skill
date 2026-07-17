from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class RecordingSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


def _factory(session: RecordingSession):
    return lambda: session


def test_get_db_commits_successful_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from server import db

    session = RecordingSession()
    monkeypatch.setattr(db, "get_session_factory", lambda: _factory(session))
    dependency = db.get_db()

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)

    assert (session.commits, session.rollbacks, session.closes) == (1, 0, 1)


def test_get_db_rolls_back_failed_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from server import db

    session = RecordingSession()
    monkeypatch.setattr(db, "get_session_factory", lambda: _factory(session))
    dependency = db.get_db()

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="boom"):
        dependency.throw(RuntimeError("boom"))

    assert (session.commits, session.rollbacks, session.closes) == (0, 1, 1)


def test_session_scope_owns_background_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    from server import db

    session = RecordingSession()
    monkeypatch.setattr(db, "get_session_factory", lambda: _factory(session))

    context: AbstractContextManager[Any] = db.session_scope()
    with context as yielded:
        assert yielded is session

    assert (session.commits, session.rollbacks, session.closes) == (1, 0, 1)


def test_domain_services_do_not_own_transactions() -> None:
    root = Path(__file__).resolve().parents[2]
    service_paths = sorted((root / "server" / "modules").glob("*/service.py"))
    violations = []
    for path in service_paths:
        text = path.read_text(encoding="utf-8")
        if ".commit(" in text or ".rollback(" in text:
            violations.append(path.relative_to(root).as_posix())
    assert not violations, "domain services own transactions: " + ", ".join(violations)


def test_lifespan_initializes_database_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from server import lifecycle
    from server.app import create_app

    calls = []
    monkeypatch.setattr(lifecycle, "ensure_database_ready", lambda settings: calls.append(settings))
    app = create_app()

    async def exercise_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert calls == [app.state.settings]

    import asyncio

    asyncio.run(exercise_lifespan())
    assert calls == [app.state.settings]


def test_service_participates_in_callers_transaction(tmp_path: Path) -> None:
    import server.model_registry  # noqa: F401
    from server.model_base import Base
    from server.modules.authoring.models import Skill
    from server.modules.authoring.schemas import SkillCreateRequest
    from server.modules.authoring.service import create_skill
    from server.modules.identity.models import Principal

    engine = create_engine(f"sqlite:///{tmp_path / 'service-transaction.db'}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            principal = Principal(kind="user", slug="owner", display_name="Owner")
            session.add(principal)
            session.flush()
            skill = create_skill(
                session,
                namespace_id=principal.id,
                actor_principal_id=principal.id,
                payload=SkillCreateRequest(slug="transactional", display_name="Transactional"),
            )
            assert skill.id is not None
            session.rollback()

        with Session(engine) as session:
            assert session.scalar(select(Skill).where(Skill.slug == "transactional")) is None
    finally:
        engine.dispose()
