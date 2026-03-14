from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.submissions import latest_review, serialize_submission
from server.api.jobs import router as jobs_router
from server.api.reviews import router as reviews_router
from server.api.submissions import router as submissions_router
from server.api.skills import router as skills_router
from server.api.reviews import serialize_review
from server.auth import get_current_user, require_registry_reader, require_role
from server.db import ensure_database_ready, get_db
from server.jobs import serialize_job
from server.models import Job, Review, Submission, User
from server.settings import get_settings


def _artifact_file_response(artifact_root: Path, *segments: str) -> FileResponse:
    artifact_root = artifact_root.resolve()
    candidate = artifact_root.joinpath(*segments).resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='artifact not found') from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail='artifact not found')
    return FileResponse(candidate)


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()
    app = FastAPI(title='infinitas hosted registry')
    registry_router = APIRouter(
        prefix='/registry',
        tags=['hosted-registry'],
        dependencies=[Depends(require_registry_reader)],
    )

    @registry_router.get('/ai-index.json')
    def registry_ai_index():
        return _artifact_file_response(settings.artifact_path, 'ai-index.json')

    @registry_router.get('/distributions.json')
    def registry_distributions():
        return _artifact_file_response(settings.artifact_path, 'distributions.json')

    @registry_router.get('/compatibility.json')
    def registry_compatibility():
        return _artifact_file_response(settings.artifact_path, 'compatibility.json')

    @registry_router.get('/discovery-index.json')
    def registry_discovery():
        return _artifact_file_response(settings.artifact_path, 'discovery-index.json')

    @registry_router.get('/skills/{publisher}/{skill}/{version}/{filename}')
    def registry_skill_artifact(publisher: str, skill: str, version: str, filename: str):
        return _artifact_file_response(settings.artifact_path, 'skills', publisher, skill, version, filename)

    @registry_router.get('/provenance/{filename}')
    def registry_provenance(filename: str):
        return _artifact_file_response(settings.artifact_path, 'provenance', filename)

    @registry_router.get('/catalog/{catalog_path:path}')
    def registry_catalog_artifact(catalog_path: str):
        return _artifact_file_response(settings.artifact_path, 'catalog', catalog_path)

    @app.get('/healthz')
    def healthz(db: Session = Depends(get_db)):
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        return {'ok': True, 'service': settings.app_name, 'users': user_count}

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request, db: Session = Depends(get_db)):
        context = {
            'request': request,
            'app_name': settings.app_name,
            'database_url': settings.database_url,
            'user_count': db.scalar(select(func.count()).select_from(User)) or 0,
            'submission_count': db.scalar(select(func.count()).select_from(Submission)) or 0,
            'job_count': db.scalar(select(func.count()).select_from(Job)) or 0,
        }
        return templates.TemplateResponse('index.html', context)

    @app.get('/submissions', response_class=HTMLResponse)
    def submissions_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        _: User = Depends(require_role('maintainer')),
        db: Session = Depends(get_db),
    ):
        rows = (
            db.query(Submission)
            .order_by(Submission.updated_at.desc(), Submission.id.desc())
            .limit(limit)
            .all()
        )
        context = {
            'request': request,
            'title': 'Submissions',
            'content': 'Latest hosted submissions for maintainers.',
            'items': [serialize_submission(row, latest_review(db, row.id)).model_dump() for row in rows],
            'limit': limit,
        }
        return templates.TemplateResponse('submissions.html', context)

    @app.get('/reviews', response_class=HTMLResponse)
    def reviews_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        _: User = Depends(require_role('maintainer')),
        db: Session = Depends(get_db),
    ):
        rows = (
            db.query(Review)
            .order_by(Review.updated_at.desc(), Review.id.desc())
            .limit(limit)
            .all()
        )
        context = {
            'request': request,
            'title': 'Reviews',
            'content': 'Latest hosted reviews for maintainers.',
            'items': [serialize_review(row).model_dump() for row in rows],
            'limit': limit,
        }
        return templates.TemplateResponse('reviews.html', context)

    @app.get('/jobs', response_class=HTMLResponse)
    def jobs_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        _: User = Depends(require_role('maintainer')),
        db: Session = Depends(get_db),
    ):
        rows = (
            db.query(Job)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(limit)
            .all()
        )
        context = {
            'request': request,
            'title': 'Jobs',
            'content': 'Latest hosted jobs for maintainers.',
            'items': [serialize_job(row).model_dump() for row in rows],
            'limit': limit,
        }
        return templates.TemplateResponse('jobs.html', context)

    @app.get('/login', response_class=HTMLResponse)
    def login(request: Request):
        return templates.TemplateResponse(
            'layout.html',
            {
                'request': request,
                'title': 'Login',
                'content': 'Use a bearer token created by the hosted registry control plane to access API routes.',
            },
        )

    @app.get('/api/v1/me')
    def read_me(user: User = Depends(get_current_user)):
        return {
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'role': user.role,
        }

    app.include_router(submissions_router)
    app.include_router(reviews_router)
    app.include_router(skills_router)
    app.include_router(jobs_router)
    app.include_router(registry_router)

    return app


app = create_app()
