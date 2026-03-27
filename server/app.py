from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.submissions import latest_review, serialize_submission
from server.api.jobs import router as jobs_router
from server.api.reviews import router as reviews_router
from server.api.submissions import router as submissions_router
from server.api.skills import router as skills_router
from server.api.search import router as search_router
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


def _get_skill_icon(skill: dict) -> str:
    """Get emoji icon based on skill tags/name"""
    name = skill.get('name', '').lower()
    tags = [t.lower() for t in skill.get('tags', [])]
    
    if 'discovery' in tags or 'search' in tags:
        return '🔍'
    if 'install' in tags or 'pull' in tags:
        return '📦'
    if 'release' in tags or 'publish' in tags:
        return '🚀'
    if 'operate' in tags or 'manage' in tags:
        return '🔧'
    if 'security' in tags or 'check' in tags:
        return '🔒'
    if 'consume' in name:
        return '🎯'
    if 'federation' in name:
        return '🌐'
    
    return '🎯'


def _calculate_skill_rating(skill: dict) -> float | None:
    """Calculate skill rating based on review state"""
    review_state = skill.get('review_state', '')
    approval_count = skill.get('approval_count', 0)
    
    if review_state == 'approved' and approval_count > 0:
        base = 4.5
        if approval_count >= 2:
            base = 4.8
        return round(base, 1)
    return None


def _short_stamp(value: str | None) -> str:
    if not value:
        return 'No snapshot'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return value


def _pick_lang(lang: str, zh: str, en: str) -> str:
    return zh if lang == 'zh' else en


def _resolve_language(request: Request) -> str:
    lang = (request.query_params.get('lang') or 'zh').strip().lower()
    return 'en' if lang.startswith('en') else 'zh'


def _localized_stamp(value: str | None, lang: str) -> str:
    if not value:
        return _pick_lang(lang, '暂无快照', 'No snapshot')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return value


def _build_language_switches(request: Request, lang: str) -> list[dict[str, str | bool]]:
    options = [('zh', '中'), ('en', 'EN')]
    return [
        {
            'code': code,
            'label': label,
            'href': str(request.url.include_query_params(lang=code)),
            'active': code == lang,
        }
        for code, label in options
    ]


def _build_kawaii_ui_context(request: Request, lang: str, page_kicker: str, page_eyebrow: str) -> dict:
    return {
        'page_language': lang,
        'page_lang_attr': 'zh-CN' if lang == 'zh' else 'en',
        'language_switches': _build_language_switches(request, lang),
        'theme_switches': [
            {'value': 'light', 'label': _pick_lang(lang, '浅色', 'Light')},
            {'value': 'dark', 'label': _pick_lang(lang, '深色', 'Dark')},
        ],
        'ui': {
            'brand_subtitle': _pick_lang(lang, '私有技能仓库', 'Private skill registry'),
            'theme_toggle_label': _pick_lang(lang, '主题切换', 'Theme switcher'),
            'language_toggle_label': _pick_lang(lang, '语言切换', 'Language switcher'),
            'copy_success': _pick_lang(lang, '已复制', 'Copied'),
            'copy_error': _pick_lang(lang, '复制失败', 'Copy failed'),
            'copy_icon_title': _pick_lang(lang, '复制', 'Copy'),
            'copy_button_label': _pick_lang(lang, '复制', 'Copy'),
            'status_running': _pick_lang(lang, '运行中', 'Running'),
            'page_kicker': page_kicker,
            'page_eyebrow': page_eyebrow,
            'handoff_title': _pick_lang(lang, '交接台', 'Hand-off desk'),
            'handoff_human_tab': _pick_lang(lang, '交任务', 'Delegate'),
            'handoff_agent_tab': _pick_lang(lang, '执行命令', 'Run command'),
            'copy_prompt_action': _pick_lang(lang, '复制这条提示', 'Copy this prompt'),
            'cli_mirror_label': _pick_lang(lang, '命令镜像', 'CLI mirror'),
            'console_section_title': _pick_lang(lang, '有事再进维护台', 'Open console when needed'),
            'skills_section_title': _pick_lang(lang, '常用技能', 'Popular skills'),
            'skills_section_subtitle': _pick_lang(
                lang,
                '从目录里挑 3 个入口，先检查再交给 Agent。',
                'Pick 3 likely entries, inspect first, then hand them off.',
            ),
            'featured_skill_fallback': _pick_lang(lang, '精选', 'Featured'),
            'copy_inspect_action': _pick_lang(lang, '复制检查命令', 'Copy inspect command'),
            'go_handoff_action': _pick_lang(lang, '去交接台', 'Go to hand-off'),
        },
    }


def _site_nav(home: bool, lang: str) -> list[dict[str, str]]:
    if home:
        return [
            {'href': '#start', 'label': _pick_lang(lang, '开始', 'Home base')},
            {'href': '#handoff', 'label': _pick_lang(lang, '交接', 'Handoff')},
            {'href': '#console', 'label': _pick_lang(lang, '维护台', 'Console')},
        ]
    return [
        {'href': '/', 'label': _pick_lang(lang, '首页', 'Home')},
        {'href': '/submissions', 'label': _pick_lang(lang, '提交', 'Submissions')},
        {'href': '/reviews', 'label': _pick_lang(lang, '评审', 'Reviews')},
        {'href': '/jobs', 'label': _pick_lang(lang, '任务', 'Jobs')},
    ]


def _build_home_context(settings, db: Session, request: Request) -> dict:
    lang = _resolve_language(request)
    discovery_payload = _catalog_payload(settings, 'discovery-index.json')
    featured_skills = []
    for skill in (discovery_payload.get('skills') or [])[:3]:
        publisher = skill.get('publisher') or ''
        name = skill.get('name') or ''
        qualified_name = f'{publisher}/{name}' if publisher and name else name
        summary = skill.get('summary') or _pick_lang(lang, '查看信任状态、版本和安装建议。', 'Review trust, version, and install guidance.')
        if len(summary) > 96:
            summary = summary[:93].rstrip() + '...'
        featured_skills.append(
            {
                'name': name or qualified_name or _pick_lang(lang, '未命名 skill', 'Unnamed skill'),
                'qualified_name': qualified_name,
                'publisher': publisher,
                'version': skill.get('version') or 'active',
                'summary': summary,
                'icon': _get_skill_icon(skill),
                'rating': _calculate_skill_rating(skill),
                'inspect_command': f'scripts/inspect-skill.sh {qualified_name}' if qualified_name else '',
            }
        )
    pending_reviews = int(db.scalar(select(func.count()).select_from(Review).where(Review.status == 'pending')) or 0)
    queued_jobs = int(db.scalar(select(func.count()).select_from(Job).where(Job.status == 'queued')) or 0)
    running_jobs = int(db.scalar(select(func.count()).select_from(Job).where(Job.status == 'running')) or 0)
    access_mode = _pick_lang(lang, '私有', 'Private') if settings.registry_read_tokens else _pick_lang(lang, '开放', 'Open')
    operating_states = [
        {
            'icon': '🔒',
            'label': _pick_lang(lang, '模式', 'Mode'),
            'value': access_mode,
            'detail': (
                _pick_lang(lang, '需 token 读取', 'Token required')
                if settings.registry_read_tokens
                else _pick_lang(lang, '允许匿名读取', 'Anonymous read enabled')
            ),
        },
        {
            'icon': '📅',
            'label': _pick_lang(lang, '同步', 'Sync'),
            'value': _localized_stamp(discovery_payload.get('generated_at'), lang),
            'detail': _pick_lang(lang, 'catalog 快照', 'Catalog snapshot'),
        },
        {
            'icon': '⚡',
            'label': _pick_lang(lang, '队列', 'Queue'),
            'value': (
                f'{pending_reviews} 待评审 / {queued_jobs} 排队'
                if lang == 'zh'
                else f'{pending_reviews} pending / {queued_jobs} queued'
            ),
            'detail': f'{running_jobs} 运行中' if lang == 'zh' else f'{running_jobs} running',
        },
    ]
    command_examples = [
        {
            'label': _pick_lang(lang, '执行命令', 'Run command'),
            'title': _pick_lang(lang, '搜索候选', 'Search options'),
            'short_label': _pick_lang(lang, '搜索', 'Search'),
            'command': 'scripts/recommend-skill.sh "Need a codex skill for repository operations"',
        },
        {
            'label': _pick_lang(lang, '执行命令', 'Run command'),
            'title': _pick_lang(lang, '检查细节', 'Inspect details'),
            'short_label': _pick_lang(lang, '检查', 'Inspect'),
            'command': 'scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill',
        },
    ]
    human_prompts = [
        {
            'label': _pick_lang(lang, '交任务', 'Delegate'),
            'title': _pick_lang(lang, '找 skill，再给步骤', 'Find a skill, then outline steps'),
            'short_label': _pick_lang(lang, '找 skill', 'Find skill'),
            'prompt': (
                '帮我在私有技能仓库里找适合做 registry 运维的 skill，先说明风险，再给安装步骤。'
                if lang == 'zh'
                else 'Help me find a skill for registry operations in the private catalog, explain the risks first, then give me the install steps.'
            ),
        },
        {
            'label': _pick_lang(lang, '交任务', 'Delegate'),
            'title': _pick_lang(lang, '先检查，再安装', 'Inspect first, then install'),
            'short_label': _pick_lang(lang, '先检查', 'Inspect first'),
            'prompt': (
                '我需要做 immutable install。先检查来源和版本，再告诉我应该安装哪一个。'
                if lang == 'zh'
                else 'I need to do an immutable install. Inspect the source and version first, then tell me which one I should install.'
            ),
        },
    ]
    human_input_fields = (
        ['目标', '安装位置', '风险偏好']
        if lang == 'zh'
        else ['Goal', 'Install path', 'Risk level']
    )
    console_links = [
        {
            'href': '/submissions',
            'icon': '📦',
            'title': _pick_lang(lang, '提交', 'Submissions'),
            'value': str(db.scalar(select(func.count()).select_from(Submission)) or 0),
            'detail': _pick_lang(lang, '新提案', 'New proposals'),
        },
        {
            'href': '/reviews',
            'icon': '✨',
            'title': _pick_lang(lang, '评审', 'Reviews'),
            'value': str(db.scalar(select(func.count()).select_from(Review)) or 0),
            'detail': _pick_lang(lang, '审批备注', 'Decision notes'),
        },
        {
            'href': '/jobs',
            'icon': '⚙️',
            'title': _pick_lang(lang, '任务', 'Jobs'),
            'value': str(db.scalar(select(func.count()).select_from(Job)) or 0),
            'detail': _pick_lang(lang, '队列状态', 'Queue state'),
        },
    ]
    page_eyebrow = _pick_lang(lang, 'Private agent workspace / 私人技能工作台', 'Private agent workspace / personal skill desk')
    context = {
        'title': 'infinitas hosted registry',
        'page_eyebrow': page_eyebrow,
        'page_kicker': access_mode,
        'page_mode': 'home',
        'nav_links': _site_nav(home=True, lang=lang),
        'hero_title': _pick_lang(lang, '交给 Agent', 'Hand it to Agent'),
        'hero_emphasis': '',
        'hero_body': _pick_lang(lang, '搜索、检查和执行都交给它。', 'Let it search, inspect, and execute.'),
        'hero_support': _pick_lang(lang, '你只要说明目标、位置和风险。', 'You only need to name the goal, location, and risk level.'),
        'hero_primary_link': {'href': '#handoff', 'label': _pick_lang(lang, '复制任务提示', 'Copy task prompt')},
        'hero_secondary_link': {'href': '#console', 'label': _pick_lang(lang, '查看维护台', 'Open console')},
        'hero_primary_copy': human_prompts[0]['prompt'] if human_prompts else '',
        'operating_states': operating_states,
        'human_input_fields': human_input_fields,
        'human_prompts': human_prompts,
        'command_examples': command_examples,
        'console_links': console_links,
        'featured_skills': featured_skills,
        'maintainer_primary_link': {'href': '/submissions', 'label': _pick_lang(lang, '打开维护台', 'Open console')},
        'maintainer_body': _pick_lang(
            lang,
            '首页只负责交接；审批、队列和放行都在维护台。',
            'The home page is only for hand-off; approvals, queues, and release all happen in the console.',
        ),
    }
    context.update(_build_kawaii_ui_context(request, lang, access_mode, page_eyebrow))
    return context


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
    lang = _resolve_language(request)
    page_eyebrow = _pick_lang(lang, 'Maintainer-only console / 维护控制台', 'Maintainer-only console')
    page_kicker = _pick_lang(lang, '维护模式', 'Maintainer mode')
    context = {
        'request': request,
        'title': title,
        'content': content,
        'page_eyebrow': page_eyebrow,
        'page_kicker': page_kicker,
        'page_mode': 'console',
        'nav_links': _site_nav(home=False, lang=lang),
        'items': items,
        'limit': limit,
        'cli_command': cli_command,
        'page_stats': stats,
        'insight_cards': insight_cards or [],
    }
    context.update(_build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow))
    return context


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()
    app = FastAPI(title='infinitas hosted registry')
    app.mount('/static', StaticFiles(directory=str(settings.template_dir.parent / 'static')), name='static')
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
        """Legacy index page"""
        context = {
            'request': request,
            'app_name': settings.app_name,
            'database_url': settings.database_url,
            'user_count': db.scalar(select(func.count()).select_from(User)) or 0,
            'submission_count': db.scalar(select(func.count()).select_from(Submission)) or 0,
            'job_count': db.scalar(select(func.count()).select_from(Job)) or 0,
        }
        context.update(_build_home_context(settings, db, request))
        return templates.TemplateResponse('index-kawaii.html', context)
    
    @app.get('/v2')
    def index_v2_redirect():
        return RedirectResponse(url='/', status_code=307)

    @app.get('/submissions', response_class=HTMLResponse)
    def submissions_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        _: User = Depends(require_role('maintainer')),
        db: Session = Depends(get_db),
    ):
        lang = _resolve_language(request)
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
            title=_pick_lang(lang, 'Submissions 提交队列', 'Submissions queue'),
            content=_pick_lang(
                lang,
                '查看新提案、当前评审状态，以及哪些 skill 已经接近进入后续校验和发布流程。',
                'Review new proposals, current review state, and which skills are close to validation and release.',
            ),
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> submissions list',
            stats=[
                {'value': str(len(items)), 'label': _pick_lang(lang, '当前可见', 'Visible now'), 'detail': f'limit {limit}'},
                {
                    'value': str(review_requested),
                    'label': _pick_lang(lang, '等待评审', 'Waiting review'),
                    'detail': _pick_lang(lang, '需要 maintainer 介入', 'Maintainer decision needed'),
                },
                {
                    'value': str(approved),
                    'label': _pick_lang(lang, '已批准', 'Approved'),
                    'detail': _pick_lang(lang, '可以进入后续动作', 'Ready for next actions'),
                },
            ],
            insight_cards=[
                {
                    'title': _pick_lang(lang, 'Submission cues / 提交判断', 'Submission cues'),
                    'body': _pick_lang(
                        lang,
                        '先看 status 和 review 字段，再决定是继续 request-review、排队 validation，还是直接返回提案人补信息。',
                        'Start with status and review fields, then decide to request review, queue validation, or send back for missing context.',
                    ),
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
        lang = _resolve_language(request)
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
            title=_pick_lang(lang, 'Reviews 评审台', 'Reviews desk'),
            content=_pick_lang(
                lang,
                '集中看评审决策、review note 和 pending 项，让人类能快速判断该批准、拒绝，还是先补证据。',
                'Review decisions, review notes, and pending items in one place so maintainers can approve, reject, or request more evidence quickly.',
            ),
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews list',
            stats=[
                {'value': str(len(items)), 'label': _pick_lang(lang, '当前可见', 'Visible now'), 'detail': f'limit {limit}'},
                {
                    'value': str(pending),
                    'label': _pick_lang(lang, '待决策', 'Pending decision'),
                    'detail': _pick_lang(lang, '等待 maintainer 决策', 'Waiting for a maintainer decision'),
                },
                {
                    'value': str(approved),
                    'label': _pick_lang(lang, '已批准', 'Approved'),
                    'detail': _pick_lang(lang, '已通过当前 gate', 'Already cleared'),
                },
            ],
            insight_cards=[
                {
                    'title': _pick_lang(lang, 'Decision hints / 决策提示', 'Decision hints'),
                    'body': _pick_lang(
                        lang,
                        'Pending 说明还没有 maintainer 最终决策；approved 说明该条目已经通过当前 review gate，可以看是否进入 queue-validation 或 publish。',
                        'Pending means no final maintainer decision yet; approved means the item passed the current review gate and can move toward queue-validation or publish.',
                    ),
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews list',
                },
                {
                    'title': _pick_lang(lang, 'Approve quickly / 快速放行', 'Approve quickly'),
                    'body': _pick_lang(
                        lang,
                        '如果 note 足够明确、submission 状态一致，而且 reviewer 身份可信，就可以快速批准；否则先回到 submissions 看上下文。',
                        'When the note is clear, the submission state is consistent, and reviewer identity is trusted, approve quickly; otherwise return to submissions for context.',
                    ),
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
        lang = _resolve_language(request)
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
            title=_pick_lang(lang, 'Jobs 任务台', 'Jobs desk'),
            content=_pick_lang(
                lang,
                '观察 worker 队列节奏：哪些 job 还在排队，哪些刚完成，哪些可能需要人类重新检查 submission 或 review 前置条件。',
                'Track worker queue rhythm: which jobs are queued, which just finished, and which may require a maintainer to re-check submission or review prerequisites.',
            ),
            limit=limit,
            items=items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> jobs list',
            stats=[
                {'value': str(len(items)), 'label': _pick_lang(lang, '当前可见', 'Visible now'), 'detail': f'limit {limit}'},
                {
                    'value': str(queued),
                    'label': _pick_lang(lang, '排队中', 'Queued'),
                    'detail': _pick_lang(lang, '等待 worker 轮询', 'Waiting for the worker loop'),
                },
                {
                    'value': str(completed),
                    'label': _pick_lang(lang, '已完成', 'Completed'),
                    'detail': _pick_lang(lang, '最近完成', 'Finished recently'),
                },
            ],
            insight_cards=[
                {
                    'title': _pick_lang(lang, 'Queue health / 队列健康', 'Queue health'),
                    'body': _pick_lang(
                        lang,
                        '看 queued / running / completed 的比例。queued 很多通常意味着 worker 还没跟上，或者前置 review / validation 节点正在堆积。',
                        'Watch the ratio of queued, running, and completed. A high queued count usually means workers are lagging or upstream review/validation is backing up.',
                    ),
                    'command': f'queued={queued} running={running} completed={completed}',
                },
                {
                    'title': _pick_lang(lang, 'Worker rhythm / Worker 节奏', 'Worker rhythm'),
                    'body': _pick_lang(
                        lang,
                        'Validation、promote、publish 这些 job 应该和 submission 状态变化相互对应。如果 job note 和当前 submission 状态对不上，就该回头查队列原因。',
                        'Validation, promote, and publish jobs should align with submission state changes. If job notes do not match current submission state, inspect queue causes first.',
                    ),
                    'command': 'python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> jobs list',
                },
            ],
        )
        return templates.TemplateResponse('jobs.html', context)

    @app.get('/login', response_class=HTMLResponse)
    def login(request: Request):
        lang = _resolve_language(request)
        page_eyebrow = _pick_lang(lang, 'Maintainer-only console / 维护控制台', 'Maintainer-only console')
        page_kicker = _pick_lang(lang, '认证入口', 'Auth entry')
        content = _pick_lang(
            lang,
            '使用由托管控制台签发的 Bearer Token 调用 API 路由。',
            'Use a bearer token created by the hosted control plane to access API routes.',
        )
        return templates.TemplateResponse(
            'login-kawaii.html',
            {
                'request': request,
                'title': 'Login',
                'content': content,
                'page_eyebrow': page_eyebrow,
                'page_kicker': page_kicker,
                'page_mode': 'console',
                'nav_links': _site_nav(home=False, lang=lang),
                'cli_command': 'curl -H "Authorization: Bearer <token>" https://skills.example.com/api/v1/me',
                'page_stats': [
                    {
                        'value': _pick_lang(lang, 'Bearer Token', 'Bearer Token'),
                        'label': _pick_lang(lang, '认证方式', 'Auth scheme'),
                        'detail': _pick_lang(lang, '由控制台签发', 'Issued by control plane'),
                    },
                    {
                        'value': '/api/v1/me',
                        'label': _pick_lang(lang, '首个检查点', 'First probe'),
                        'detail': _pick_lang(lang, '验证 token 是否生效', 'Validate token works'),
                    },
                    {
                        'value': '/submissions',
                        'label': _pick_lang(lang, '维护入口', 'Maintainer entry'),
                        'detail': _pick_lang(lang, '仅 maintainer 可访问', 'Maintainer role required'),
                    },
                ],
                **_build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow),
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
    app.include_router(search_router)

    return app


app = create_app()
