from __future__ import annotations

import json
from datetime import datetime
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


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _catalog_payload(settings, name: str) -> dict:
    for root in (settings.artifact_path, settings.root_dir / 'catalog'):
        payload = _read_json(root / name)
        if payload:
            return payload
    return {}


def _short_stamp(value: str | None) -> str:
    if not value:
        return 'No snapshot'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return value


def _site_nav(home: bool) -> list[dict[str, str]]:
    if home:
        return [
            {'href': '#start', 'label': '开始'},
            {'href': '#handoff', 'label': '交接'},
            {'href': '#console', 'label': '维护台'},
        ]
    return [
        {'href': '/', 'label': '首页'},
        {'href': '/submissions', 'label': '提交'},
        {'href': '/reviews', 'label': '评审'},
        {'href': '/jobs', 'label': '任务'},
    ]


def _build_home_context(settings, db: Session) -> dict:
    discovery_payload = _catalog_payload(settings, 'discovery-index.json')
    pending_reviews = int(db.scalar(select(func.count()).select_from(Review).where(Review.status == 'pending')) or 0)
    queued_jobs = int(db.scalar(select(func.count()).select_from(Job).where(Job.status == 'queued')) or 0)
    running_jobs = int(db.scalar(select(func.count()).select_from(Job).where(Job.status == 'running')) or 0)
    access_mode = '私有' if settings.registry_read_tokens else '开放'
    operating_states = [
        {
            'label': '模式',
            'value': access_mode,
            'detail': '需 token 读取' if settings.registry_read_tokens else '允许匿名读取',
        },
        {
            'label': '同步',
            'value': _short_stamp(discovery_payload.get('generated_at')),
            'detail': 'catalog 快照',
        },
        {
            'label': '队列',
            'value': f'{pending_reviews} 待评审 / {queued_jobs} 排队',
            'detail': f'{running_jobs} 运行中',
        },
    ]
    command_examples = [
        {
            'label': '执行命令',
            'title': '搜索候选',
            'short_label': '搜索',
            'command': 'scripts/recommend-skill.sh "Need a codex skill for repository operations"',
        },
        {
            'label': '执行命令',
            'title': '检查细节',
            'short_label': '检查',
            'command': 'scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill',
        },
    ]
    human_prompts = [
        {
            'label': '交任务',
            'title': '找 skill，再给步骤',
            'short_label': '找 skill',
            'prompt': (
                '帮我在私有技能仓库里找适合做 registry 运维的 skill，先说明风险，再给安装步骤。'
            ),
        },
        {
            'label': '交任务',
            'title': '先检查，再安装',
            'short_label': '先检查',
            'prompt': (
                '我需要做 immutable install。先检查来源和版本，再告诉我应该安装哪一个。'
            ),
        },
    ]
    human_input_fields = ['目标', '安装位置', '风险偏好']
    console_links = [
        {
            'href': '/submissions',
            'title': '提交',
            'value': str(db.scalar(select(func.count()).select_from(Submission)) or 0),
            'detail': '新提案',
        },
        {
            'href': '/reviews',
            'title': '评审',
            'value': str(db.scalar(select(func.count()).select_from(Review)) or 0),
            'detail': '审批备注',
        },
        {
            'href': '/jobs',
            'title': '任务',
            'value': str(db.scalar(select(func.count()).select_from(Job)) or 0),
            'detail': '队列状态',
        },
    ]
    return {
        'title': 'infinitas hosted registry',
        'page_eyebrow': 'Private agent workspace / 私人技能工作台',
        'page_kicker': access_mode,
        'page_mode': 'home',
        'nav_links': _site_nav(home=True),
        'hero_title': '交给 Agent',
        'hero_emphasis': '',
        'hero_body': '搜索、检查和执行都交给它。',
        'hero_support': '你只要说明目标、位置和风险。',
        'hero_primary_link': {'href': '#handoff', 'label': '复制提示'},
        'hero_secondary_link': {'href': '#console', 'label': '维护台'},
        'hero_primary_copy': human_prompts[0]['prompt'] if human_prompts else '',
        'operating_states': operating_states,
        'human_input_fields': human_input_fields,
        'human_prompts': human_prompts,
        'command_examples': command_examples,
        'console_links': console_links,
        'maintainer_primary_link': {'href': '/submissions', 'label': '进入维护台'},
        'maintainer_body': '首页只负责交接；审批、队列和放行都在维护台。',
    }


def _build_console_context(
    *,
    request: Request,
    title: str,
    content: str,
    limit: int,
    items: list[dict],
    cli_command: str,
    stats: list[dict[str, str]],
    insight_cards: list[dict[str, str]] | None = None,
) -> dict:
    return {
        'request': request,
        'title': title,
        'content': content,
        'page_eyebrow': 'Maintainer-only console / 维护控制台',
        'page_mode': 'console',
        'nav_links': _site_nav(home=False),
        'items': items,
        'limit': limit,
        'cli_command': cli_command,
        'page_stats': stats,
        'insight_cards': insight_cards or [],
    }


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
        context.update(_build_home_context(settings, db))
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
        items = [serialize_submission(row, latest_review(db, row.id)).model_dump() for row in rows]
        review_requested = sum(1 for item in items if item.get('status') == 'review_requested')
        approved = sum(1 for item in items if item.get('status') == 'approved')
        context = _build_console_context(
            request=request,
            title='Submissions 提交队列',
            content='查看新提案、当前评审状态，以及哪些 skill 已经接近进入后续校验和发布流程。',
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> submissions list',
            stats=[
                {'value': str(len(items)), 'label': '当前可见', 'detail': f'limit {limit}'},
                {'value': str(review_requested), 'label': '等待评审', 'detail': '需要 maintainer 介入'},
                {'value': str(approved), 'label': '已批准', 'detail': '可以进入后续动作'},
            ],
            insight_cards=[
                {
                    'title': 'Submission cues / 提交判断',
                    'body': '先看 status 和 review 字段，再决定是继续 request-review、排队 validation，还是直接返回提案人补信息。',
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> submissions list',
                }
            ],
        )
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
        items = [serialize_review(row).model_dump() for row in rows]
        approved = sum(1 for item in items if item.get('status') == 'approved')
        pending = sum(1 for item in items if item.get('status') == 'pending')
        context = _build_console_context(
            request=request,
            title='Reviews 评审台',
            content='集中看评审决策、review note 和 pending 项，让人类能快速判断该批准、拒绝，还是先补证据。',
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews list',
            stats=[
                {'value': str(len(items)), 'label': '当前可见', 'detail': f'limit {limit}'},
                {'value': str(pending), 'label': '待决策', 'detail': 'waiting for a maintainer decision'},
                {'value': str(approved), 'label': '已批准', 'detail': 'already cleared'},
            ],
            insight_cards=[
                {
                    'title': 'Decision hints / 决策提示',
                    'body': 'Pending 说明还没有 maintainer 最终决策；approved 说明该条目已经通过当前 review gate，可以看是否进入 queue-validation 或 publish。',
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews list',
                },
                {
                    'title': 'Approve quickly / 快速放行',
                    'body': '如果 note 足够明确、submission 状态一致，而且 reviewer 身份可信，就可以快速批准；否则先回到 submissions 看上下文。',
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews approve <review-id> --note "Looks good"',
                },
            ],
        )
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
        items = [serialize_job(row).model_dump() for row in rows]
        queued = sum(1 for item in items if item.get('status') == 'queued')
        completed = sum(1 for item in items if item.get('status') == 'completed')
        running = sum(1 for item in items if item.get('status') == 'running')
        context = _build_console_context(
            request=request,
            title='Jobs 任务台',
            content='观察 worker 队列节奏：哪些 job 还在排队，哪些刚完成，哪些可能需要人类重新检查 submission 或 review 前置条件。',
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> jobs list',
            stats=[
                {'value': str(len(items)), 'label': '当前可见', 'detail': f'limit {limit}'},
                {'value': str(queued), 'label': '排队中', 'detail': 'waiting for the worker loop'},
                {'value': str(completed), 'label': '已完成', 'detail': 'finished recently'},
            ],
            insight_cards=[
                {
                    'title': 'Queue health / 队列健康',
                    'body': '看 queued / running / completed 的比例。queued 很多通常意味着 worker 还没跟上，或者前置 review / validation 节点正在堆积。',
                    'command': f'queued={queued} running={running} completed={completed}',
                },
                {
                    'title': 'Worker rhythm / Worker 节奏',
                    'body': 'Validation、promote、publish 这些 job 应该和 submission 状态变化相互对应。如果 job note 和当前 submission 状态对不上，就该回头查队列原因。',
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> jobs list',
                },
            ],
        )
        return templates.TemplateResponse('jobs.html', context)

    @app.get('/login', response_class=HTMLResponse)
    def login(request: Request):
        return templates.TemplateResponse(
            'layout.html',
            {
                'request': request,
                'title': 'Login',
                'content': 'Use a bearer token created by the hosted registry control plane to access API routes.',
                'page_eyebrow': 'Maintainer-only console',
                'page_mode': 'console',
                'nav_links': _site_nav(home=False),
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
