"""Repository pattern for data access isolation.

This package provides repository implementations that isolate
the service layer from SQLAlchemy ORM details.

Example usage:
    from server.repository.base import SQLAlchemyUnitOfWork
    from server.modules.authoring.repositories import SkillRepository

    class MyService:
        def __init__(self, session: Session):
            self.skill_repo = SkillRepository(session)

    # In FastAPI route:
    @app.get("/skills/{skill_id}")
    def get_skill(skill_id: int, db: Session = Depends(get_db)):
        service = MyService(db)
        skill = service.skill_repo.get_or_404(skill_id)
        return skill
"""

from server.repository.base import (
    QueryBuilder,
    Repository,
    SQLAlchemyRepository,
    SQLAlchemyUnitOfWork,
    UnitOfWork,
)

__all__ = [
    "Repository",
    "SQLAlchemyRepository",
    "UnitOfWork",
    "SQLAlchemyUnitOfWork",
    "QueryBuilder",
]
