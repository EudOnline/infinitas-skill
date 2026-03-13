from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.reviews import router as reviews_router
from server.api.skills import router as skills_router
from server.api.submissions import router as submissions_router
from server.auth import get_current_user
from server.db import ensure_database_ready, get_db
from server.models import Job, Submission, User
from server.settings import get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.template_dir))


def create_app() -> FastAPI:
    ensure_database_ready()
    app = FastAPI(title='infinitas hosted registry')

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

    return app


app = create_app()
