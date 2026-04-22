"""Private-first hosted registry CLI wired into the unified infinitas command."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

REGISTRY_TOP_LEVEL_HELP = 'Hosted registry control-plane tools'
REGISTRY_PARSER_DESCRIPTION = 'Hosted registry private-first control plane CLI'


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def request_json(args, method: str, path: str, payload: dict | None = None):
    headers = {}
    if args.token:
        headers['Authorization'] = f'Bearer {args.token}'
    try:
        response = httpx.request(method, args.base_url.rstrip('/') + path, json=payload, headers=headers, timeout=30.0)
    except httpx.HTTPError as exc:
        fail(f'API request failed: {exc}')
    if response.status_code >= 400:
        fail(response.text)
    if response.content:
        return response.json()
    return {'ok': True}


def command_access_me(args):
    return request_json(args, 'GET', '/api/v1/access/me')


def command_access_check_release(args):
    return request_json(args, 'GET', f'/api/v1/access/releases/{args.release_id}/check')


def command_authoring_get_skill(args):
    return request_json(args, 'GET', f'/api/v1/skills/{args.skill_id}')


def _parse_json_object(raw: str, *, arg_name: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f'invalid {arg_name}: {exc}')
    if not isinstance(payload, dict):
        fail(f'invalid {arg_name}: expected JSON object')
    return payload


def command_authoring_create_skill(args):
    return request_json(
        args,
        'POST',
        '/api/v1/skills',
        {
            'slug': args.slug,
            'display_name': args.display_name,
            'summary': args.summary,
            'default_visibility_profile': args.default_visibility_profile,
        },
    )


def command_authoring_create_draft(args):
    metadata = _parse_json_object(args.metadata_json, arg_name='--metadata-json')
    payload = {
        'base_version_id': args.base_version_id,
        'content_ref': args.content_ref,
        'metadata': metadata,
    }
    return request_json(args, 'POST', f'/api/v1/skills/{args.skill_id}/drafts', payload)


def command_authoring_patch_draft(args):
    payload = {}
    if args.content_ref is not None:
        payload['content_ref'] = args.content_ref
    if args.metadata_json is not None:
        payload['metadata'] = _parse_json_object(args.metadata_json, arg_name='--metadata-json')
    if not payload:
        fail('drafts update requires at least one of --content-ref or --metadata-json')
    return request_json(args, 'PATCH', f'/api/v1/drafts/{args.draft_id}', payload)


def command_authoring_seal_draft(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/drafts/{args.draft_id}/seal',
        {'version': args.version},
    )


def command_agent_preset_create(args):
    return request_json(
        args,
        'POST',
        '/api/v1/agent-presets',
        {
            'slug': args.slug,
            'display_name': args.display_name,
            'summary': args.summary,
            'runtime_family': args.runtime_family,
            'supported_memory_modes': args.supported_memory_modes,
            'default_memory_mode': args.default_memory_mode,
            'pinned_skill_dependencies': args.pinned_skill_dependencies,
        },
    )


def command_agent_preset_create_draft(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/agent-presets/{args.preset_id}/drafts',
        {
            'prompt': args.prompt,
            'model': args.model,
            'tools': args.tools,
        },
    )


def command_agent_preset_seal_draft(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/agent-preset-drafts/{args.draft_id}/seal',
        {'version': args.version},
    )


def command_agent_code_create(args):
    return request_json(
        args,
        'POST',
        '/api/v1/agent-codes',
        {
            'slug': args.slug,
            'display_name': args.display_name,
            'summary': args.summary,
            'runtime_family': args.runtime_family,
            'language': args.language,
            'entrypoint': args.entrypoint,
        },
    )


def command_agent_code_create_draft(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/agent-codes/{args.code_id}/drafts',
        {'content_ref': args.content_ref},
    )


def command_agent_code_seal_draft(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/agent-code-drafts/{args.draft_id}/seal',
        {'version': args.version},
    )


def command_release_create(args):
    return request_json(args, 'POST', f'/api/v1/versions/{args.version_id}/releases', {})


def command_release_get(args):
    return request_json(args, 'GET', f'/api/v1/releases/{args.release_id}')


def command_release_artifacts(args):
    return request_json(args, 'GET', f'/api/v1/releases/{args.release_id}/artifacts')


def command_exposure_create(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/releases/{args.release_id}/exposures',
        {
            'audience_type': args.audience_type,
            'listing_mode': args.listing_mode,
            'install_mode': args.install_mode,
            'requested_review_mode': args.requested_review_mode,
        },
    )


def command_exposure_update(args):
    payload = {}
    if args.listing_mode is not None:
        payload['listing_mode'] = args.listing_mode
    if args.install_mode is not None:
        payload['install_mode'] = args.install_mode
    if args.requested_review_mode is not None:
        payload['requested_review_mode'] = args.requested_review_mode
    if not payload:
        fail('exposures update requires at least one of --listing-mode, --install-mode, or --requested-review-mode')
    return request_json(args, 'PATCH', f'/api/v1/exposures/{args.exposure_id}', payload)


def command_exposure_activate(args):
    return request_json(args, 'POST', f'/api/v1/exposures/{args.exposure_id}/activate', {})


def command_exposure_revoke(args):
    return request_json(args, 'POST', f'/api/v1/exposures/{args.exposure_id}/revoke', {})


def command_review_open_case(args):
    payload = {}
    if args.mode:
        payload['mode'] = args.mode
    return request_json(args, 'POST', f'/api/v1/exposures/{args.exposure_id}/review-cases', payload)


def command_review_get_case(args):
    return request_json(args, 'GET', f'/api/v1/review-cases/{args.review_case_id}')


def command_review_decide(args):
    evidence = _parse_json_object(args.evidence_json, arg_name='--evidence-json')
    return request_json(
        args,
        'POST',
        f'/api/v1/review-cases/{args.review_case_id}/decisions',
        {
            'decision': args.decision,
            'note': args.note,
            'evidence': evidence,
        },
    )


def command_not_implemented(message: str):
    fail(message)


def _emit_json_result(result):
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _wrap_registry_handler(func):
    return lambda args: _emit_json_result(func(args))


def configure_registry_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        '--base-url',
        default=os.environ.get('INFINITAS_REGISTRY_API_BASE_URL', 'http://127.0.0.1:8000'),
        help='Hosted registry API base URL',
    )
    parser.add_argument(
        '--token',
        default=os.environ.get('INFINITAS_REGISTRY_API_TOKEN', ''),
        help='Bearer token for hosted registry API',
    )
    subparsers = parser.add_subparsers(
        dest='registry_command',
        metavar='{skills,drafts,agent-presets,agent-codes,releases,exposures,grants,tokens,reviews}',
    )

    skills = subparsers.add_parser('skills', help='Manage private-first skill records')
    skills_subparsers = skills.add_subparsers(dest='subcommand', metavar='{create,get}')
    skills_create = skills_subparsers.add_parser('create', help='Create a new skill namespace entry')
    skills_create.add_argument('--slug', required=True, help='Skill slug')
    skills_create.add_argument('--display-name', required=True, help='Human readable skill display name')
    skills_create.add_argument('--summary', default='', help='Skill summary')
    skills_create.add_argument(
        '--default-visibility-profile',
        default=None,
        help='Optional default visibility profile identifier',
    )
    skills_create.set_defaults(_handler=_wrap_registry_handler(command_authoring_create_skill))
    skills_get = skills_subparsers.add_parser('get', help='Fetch one skill by id')
    skills_get.add_argument('skill_id', type=int, help='Skill identifier')
    skills_get.set_defaults(_handler=_wrap_registry_handler(command_authoring_get_skill))

    drafts = subparsers.add_parser('drafts', help='Manage editable drafts and immutable version sealing')
    drafts_subparsers = drafts.add_subparsers(dest='subcommand', metavar='{create,update,seal}')
    drafts_create = drafts_subparsers.add_parser('create', help='Create an editable draft for a skill')
    drafts_create.add_argument('skill_id', type=int, help='Skill identifier')
    drafts_create.add_argument(
        '--base-version-id',
        type=int,
        default=None,
        help='Optional base skill_version id',
    )
    drafts_create.add_argument('--content-ref', default='', help='Content locator/ref used by authoring')
    drafts_create.add_argument(
        '--metadata-json',
        default='{}',
        help='Draft metadata as JSON object',
    )
    drafts_create.set_defaults(_handler=_wrap_registry_handler(command_authoring_create_draft))
    drafts_update = drafts_subparsers.add_parser('update', help='Patch an open draft')
    drafts_update.add_argument('draft_id', type=int, help='Draft identifier')
    drafts_update.add_argument('--content-ref', default=None, help='Updated content ref')
    drafts_update.add_argument('--metadata-json', default=None, help='Updated metadata JSON object')
    drafts_update.set_defaults(_handler=_wrap_registry_handler(command_authoring_patch_draft))
    drafts_seal = drafts_subparsers.add_parser('seal', help='Seal draft into an immutable skill version')
    drafts_seal.add_argument('draft_id', type=int, help='Draft identifier')
    drafts_seal.add_argument('--version', required=True, help='Semantic version to create')
    drafts_seal.set_defaults(_handler=_wrap_registry_handler(command_authoring_seal_draft))

    agent_presets = subparsers.add_parser('agent-presets', help='Manage publishable agent preset objects')
    agent_presets_subparsers = agent_presets.add_subparsers(dest='subcommand', metavar='{create,create-draft,seal-draft}')
    preset_create = agent_presets_subparsers.add_parser('create', help='Create a new agent preset object')
    preset_create.add_argument('--slug', required=True)
    preset_create.add_argument('--display-name', required=True)
    preset_create.add_argument('--summary', default='')
    preset_create.add_argument('--runtime-family', default='openclaw')
    preset_create.add_argument('--supported-memory-modes', nargs='*', default=['none'])
    preset_create.add_argument('--default-memory-mode', default='none')
    preset_create.add_argument('--pinned-skill-dependencies', nargs='*', default=[])
    preset_create.set_defaults(_handler=_wrap_registry_handler(command_agent_preset_create))
    preset_draft = agent_presets_subparsers.add_parser('create-draft', help='Create a draft payload for an agent preset')
    preset_draft.add_argument('preset_id', type=int)
    preset_draft.add_argument('--prompt', default='')
    preset_draft.add_argument('--model', default='')
    preset_draft.add_argument('--tools', nargs='*', default=[])
    preset_draft.set_defaults(_handler=_wrap_registry_handler(command_agent_preset_create_draft))
    preset_seal = agent_presets_subparsers.add_parser('seal-draft', help='Seal an agent preset draft')
    preset_seal.add_argument('draft_id', type=int)
    preset_seal.add_argument('--version', required=True)
    preset_seal.set_defaults(_handler=_wrap_registry_handler(command_agent_preset_seal_draft))

    agent_codes = subparsers.add_parser('agent-codes', help='Manage publishable agent code objects')
    agent_codes_subparsers = agent_codes.add_subparsers(dest='subcommand', metavar='{create,create-draft,seal-draft}')
    code_create = agent_codes_subparsers.add_parser('create', help='Create a new agent code object')
    code_create.add_argument('--slug', required=True)
    code_create.add_argument('--display-name', required=True)
    code_create.add_argument('--summary', default='')
    code_create.add_argument('--runtime-family', default='openclaw')
    code_create.add_argument('--language', default='python')
    code_create.add_argument('--entrypoint', required=True)
    code_create.set_defaults(_handler=_wrap_registry_handler(command_agent_code_create))
    code_draft = agent_codes_subparsers.add_parser('create-draft', help='Create an external-import draft for agent code')
    code_draft.add_argument('code_id', type=int)
    code_draft.add_argument('--content-ref', required=True)
    code_draft.set_defaults(_handler=_wrap_registry_handler(command_agent_code_create_draft))
    code_seal = agent_codes_subparsers.add_parser('seal-draft', help='Seal an agent code draft')
    code_seal.add_argument('draft_id', type=int)
    code_seal.add_argument('--version', required=True)
    code_seal.set_defaults(_handler=_wrap_registry_handler(command_agent_code_seal_draft))

    releases = subparsers.add_parser('releases', help='Create and inspect immutable releases')
    releases_subparsers = releases.add_subparsers(dest='subcommand', metavar='{create,get,artifacts}')
    releases_create = releases_subparsers.add_parser('create', help='Create or fetch a release for one skill version')
    releases_create.add_argument('version_id', type=int, help='Skill version identifier')
    releases_create.set_defaults(_handler=_wrap_registry_handler(command_release_create))
    releases_get = releases_subparsers.add_parser('get', help='Fetch one release by id')
    releases_get.add_argument('release_id', type=int, help='Release identifier')
    releases_get.set_defaults(_handler=_wrap_registry_handler(command_release_get))
    releases_artifacts = releases_subparsers.add_parser('artifacts', help='List artifacts for one release')
    releases_artifacts.add_argument('release_id', type=int, help='Release identifier')
    releases_artifacts.set_defaults(_handler=_wrap_registry_handler(command_release_artifacts))

    exposures = subparsers.add_parser('exposures', help='Manage audience exposure and share policy')
    exposures_subparsers = exposures.add_subparsers(dest='subcommand', metavar='{create,update,activate,revoke}')
    exposures_create = exposures_subparsers.add_parser('create', help='Create a new audience exposure for one release')
    exposures_create.add_argument('release_id', type=int, help='Release identifier')
    exposures_create.add_argument('--audience-type', required=True, help='Audience type: private, grant, or public')
    exposures_create.add_argument('--listing-mode', default='listed', help='Listing mode')
    exposures_create.add_argument('--install-mode', default='enabled', help='Install mode')
    exposures_create.add_argument('--requested-review-mode', default='none', help='Requested review mode')
    exposures_create.set_defaults(_handler=_wrap_registry_handler(command_exposure_create))
    exposures_update = exposures_subparsers.add_parser('update', help='Patch share policy on an existing exposure')
    exposures_update.add_argument('exposure_id', type=int, help='Exposure identifier')
    exposures_update.add_argument('--listing-mode', default=None, help='Updated listing mode')
    exposures_update.add_argument('--install-mode', default=None, help='Updated install mode')
    exposures_update.add_argument('--requested-review-mode', default=None, help='Updated requested review mode')
    exposures_update.set_defaults(_handler=_wrap_registry_handler(command_exposure_update))
    exposures_activate = exposures_subparsers.add_parser('activate', help='Activate an exposure')
    exposures_activate.add_argument('exposure_id', type=int, help='Exposure identifier')
    exposures_activate.set_defaults(_handler=_wrap_registry_handler(command_exposure_activate))
    exposures_revoke = exposures_subparsers.add_parser('revoke', help='Revoke an exposure')
    exposures_revoke.add_argument('exposure_id', type=int, help='Exposure identifier')
    exposures_revoke.set_defaults(_handler=_wrap_registry_handler(command_exposure_revoke))

    grants = subparsers.add_parser('grants', help='Inspect grant policy scaffolding for token-scoped access')
    grants_subparsers = grants.add_subparsers(dest='subcommand', metavar='{list,create-token,revoke}')
    grants_list = grants_subparsers.add_parser('list', help='Reserved command for upcoming grant listing APIs')
    grants_list.set_defaults(_handler=_wrap_registry_handler(lambda _args: command_not_implemented('grant listing API is not available yet')))
    grants_create_token = grants_subparsers.add_parser('create-token', help='Reserved command for issuing grant tokens')
    grants_create_token.add_argument('grant_id', type=int, help='Grant identifier')
    grants_create_token.set_defaults(
        _handler=_wrap_registry_handler(lambda _args: command_not_implemented('grant token issuing API is not available yet'))
    )
    grants_revoke = grants_subparsers.add_parser('revoke', help='Reserved command for revoking a grant')
    grants_revoke.add_argument('grant_id', type=int, help='Grant identifier')
    grants_revoke.set_defaults(_handler=_wrap_registry_handler(lambda _args: command_not_implemented('grant revoke API is not available yet')))

    tokens = subparsers.add_parser('tokens', help='Inspect token identity and release authorization')
    tokens_subparsers = tokens.add_subparsers(dest='subcommand', metavar='{me,check-release}')
    tokens_me = tokens_subparsers.add_parser('me', help='Show the current access identity from the bearer token')
    tokens_me.set_defaults(_handler=_wrap_registry_handler(command_access_me))
    tokens_check = tokens_subparsers.add_parser('check-release', help='Check release access for the current credential')
    tokens_check.add_argument('release_id', type=int, help='Release identifier')
    tokens_check.set_defaults(_handler=_wrap_registry_handler(command_access_check_release))

    reviews = subparsers.add_parser('reviews', help='Manage review cases for public-facing exposures')
    reviews_subparsers = reviews.add_subparsers(dest='subcommand', metavar='{open-case,get-case,decide}')
    reviews_open = reviews_subparsers.add_parser('open-case', help='Open a review case for one exposure')
    reviews_open.add_argument('exposure_id', type=int, help='Exposure identifier')
    reviews_open.add_argument('--mode', default=None, help='Optional review mode override')
    reviews_open.set_defaults(_handler=_wrap_registry_handler(command_review_open_case))
    reviews_get = reviews_subparsers.add_parser('get-case', help='Fetch one review case by id')
    reviews_get.add_argument('review_case_id', type=int, help='Review case identifier')
    reviews_get.set_defaults(_handler=_wrap_registry_handler(command_review_get_case))
    reviews_decide = reviews_subparsers.add_parser('decide', help='Record a review decision')
    reviews_decide.add_argument('review_case_id', type=int, help='Review case identifier')
    reviews_decide.add_argument('--decision', required=True, help='Decision: approve, reject, or comment')
    reviews_decide.add_argument('--note', default='', help='Decision note')
    reviews_decide.add_argument('--evidence-json', default='{}', help='Evidence JSON object')
    reviews_decide.set_defaults(_handler=_wrap_registry_handler(command_review_decide))

    return parser


def build_registry_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=REGISTRY_PARSER_DESCRIPTION, prog=prog)
    return configure_registry_parser(parser)


def _add_common_args(parser):
    parser.add_argument(
        '--base-url',
        default=os.environ.get('INFINITAS_REGISTRY_API_BASE_URL', 'http://127.0.0.1:8000'),
        help='Hosted registry API base URL',
    )
    parser.add_argument(
        '--token',
        default=os.environ.get('INFINITAS_REGISTRY_API_TOKEN', ''),
        help='Bearer token for hosted registry API',
    )


def build_registry_skills_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry skills',
        description='Manage private-first skill records',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,get}')
    create = sub.add_parser('create', help='Create a new skill namespace entry')
    create.add_argument('--slug', required=True, help='Skill slug')
    create.add_argument('--display-name', required=True, help='Human readable skill display name')
    create.add_argument('--summary', default='', help='Skill summary')
    create.add_argument('--default-visibility-profile', default=None, help='Default visibility profile')
    get = sub.add_parser('get', help='Fetch one skill by id')
    get.add_argument('skill_id', type=int, help='Skill identifier')
    return parser


def build_registry_drafts_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry drafts',
        description='Manage editable drafts and immutable version sealing',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,update,seal}')
    create = sub.add_parser('create', help='Create an editable draft for a skill')
    create.add_argument('skill_id', type=int, help='Skill identifier')
    create.add_argument('--base-version-id', type=int, default=None, help='Base skill_version id')
    create.add_argument('--content-ref', default='', help='Content locator/ref used by authoring')
    create.add_argument('--metadata-json', default='{}', help='Draft metadata as JSON object')
    update = sub.add_parser('update', help='Patch an open draft')
    update.add_argument('draft_id', type=int, help='Draft identifier')
    update.add_argument('--content-ref', default=None, help='Updated content ref')
    update.add_argument('--metadata-json', default=None, help='Updated metadata JSON object')
    seal = sub.add_parser('seal', help='Seal draft into an immutable skill version')
    seal.add_argument('draft_id', type=int, help='Draft identifier')
    seal.add_argument('--version', required=True, help='Semantic version to create')
    return parser


def build_registry_agent_presets_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry agent-presets',
        description='Manage publishable agent preset objects',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,create-draft,seal-draft}')
    create = sub.add_parser('create', help='Create a new agent preset object')
    create.add_argument('--slug', required=True)
    create.add_argument('--display-name', required=True)
    create.add_argument('--summary', default='')
    create.add_argument('--runtime-family', default='openclaw')
    create.add_argument('--supported-memory-modes', nargs='*', default=['none'])
    create.add_argument('--default-memory-mode', default='none')
    create.add_argument('--pinned-skill-dependencies', nargs='*', default=[])
    draft = sub.add_parser('create-draft', help='Create a draft payload for an agent preset')
    draft.add_argument('preset_id', type=int)
    draft.add_argument('--prompt', default='')
    draft.add_argument('--model', default='')
    draft.add_argument('--tools', nargs='*', default=[])
    seal = sub.add_parser('seal-draft', help='Seal an agent preset draft')
    seal.add_argument('draft_id', type=int)
    seal.add_argument('--version', required=True)
    return parser


def build_registry_agent_codes_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry agent-codes',
        description='Manage publishable agent code objects',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,create-draft,seal-draft}')
    create = sub.add_parser('create', help='Create a new agent code object')
    create.add_argument('--slug', required=True)
    create.add_argument('--display-name', required=True)
    create.add_argument('--summary', default='')
    create.add_argument('--runtime-family', default='openclaw')
    create.add_argument('--language', default='python')
    create.add_argument('--entrypoint', required=True)
    draft = sub.add_parser('create-draft', help='Create an external-import draft for agent code')
    draft.add_argument('code_id', type=int)
    draft.add_argument('--content-ref', required=True)
    seal = sub.add_parser('seal-draft', help='Seal an agent code draft')
    seal.add_argument('draft_id', type=int)
    seal.add_argument('--version', required=True)
    return parser


def build_registry_releases_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry releases',
        description='Create and inspect immutable releases',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,get,artifacts}')
    create = sub.add_parser('create', help='Create or fetch a release for one skill version')
    create.add_argument('version_id', type=int, help='Skill version identifier')
    get = sub.add_parser('get', help='Fetch one release by id')
    get.add_argument('release_id', type=int, help='Release identifier')
    artifacts = sub.add_parser('artifacts', help='List artifacts for one release')
    artifacts.add_argument('release_id', type=int, help='Release identifier')
    return parser


def build_registry_exposures_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry exposures',
        description='Manage audience exposure and share policy',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{create,update,activate,revoke}')
    create = sub.add_parser('create', help='Create a new audience exposure for one release')
    create.add_argument('release_id', type=int, help='Release identifier')
    create.add_argument('--audience-type', required=True, help='Audience type: private, grant, or public')
    create.add_argument('--listing-mode', default='listed', help='Listing mode')
    create.add_argument('--install-mode', default='enabled', help='Install mode')
    create.add_argument('--requested-review-mode', default='none', help='Requested review mode')
    update = sub.add_parser('update', help='Patch share policy on an existing exposure')
    update.add_argument('exposure_id', type=int, help='Exposure identifier')
    update.add_argument('--listing-mode', default=None, help='Updated listing mode')
    update.add_argument('--install-mode', default=None, help='Updated install mode')
    update.add_argument('--requested-review-mode', default=None, help='Updated requested review mode')
    activate = sub.add_parser('activate', help='Activate an exposure')
    activate.add_argument('exposure_id', type=int, help='Exposure identifier')
    revoke = sub.add_parser('revoke', help='Revoke an exposure')
    revoke.add_argument('exposure_id', type=int, help='Exposure identifier')
    return parser


def build_registry_grants_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry grants',
        description='Inspect grant policy scaffolding for token-scoped access',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{list,create-token,revoke}')
    sub.add_parser('list', help='Reserved command for upcoming grant listing APIs')
    gt = sub.add_parser('create-token', help='Reserved command for issuing grant tokens')
    gt.add_argument('grant_id', type=int, help='Grant identifier')
    gr = sub.add_parser('revoke', help='Reserved command for revoking a grant')
    gr.add_argument('grant_id', type=int, help='Grant identifier')
    return parser


def build_registry_tokens_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry tokens',
        description='Inspect token identity and release authorization',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{me,check-release}')
    sub.add_parser('me', help='Show the current access identity from the bearer token')
    check = sub.add_parser('check-release', help='Check release access for the current credential')
    check.add_argument('release_id', type=int, help='Release identifier')
    return parser


def build_registry_reviews_parser(*, prog=None):
    parser = argparse.ArgumentParser(
        prog=prog or 'infinitas registry reviews',
        description='Manage review cases for public-facing exposures',
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest='subcommand', metavar='{open-case,get-case,decide}')
    open_case = sub.add_parser('open-case', help='Open a review case for one exposure')
    open_case.add_argument('exposure_id', type=int, help='Exposure identifier')
    open_case.add_argument('--mode', default=None, help='Optional review mode override')
    get_case = sub.add_parser('get-case', help='Fetch one review case by id')
    get_case.add_argument('review_case_id', type=int, help='Review case identifier')
    decide = sub.add_parser('decide', help='Record a review decision')
    decide.add_argument('review_case_id', type=int, help='Review case identifier')
    decide.add_argument('--decision', required=True, help='Decision: approve, reject, or comment')
    decide.add_argument('--note', default='', help='Decision note')
    decide.add_argument('--evidence-json', default='{}', help='Evidence JSON object')
    return parser


def registry_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_registry_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, '_handler', None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


__all__ = [
    'REGISTRY_PARSER_DESCRIPTION',
    'REGISTRY_TOP_LEVEL_HELP',
    'build_registry_agent_codes_parser',
    'build_registry_agent_presets_parser',
    'build_registry_drafts_parser',
    'build_registry_exposures_parser',
    'build_registry_grants_parser',
    'build_registry_parser',
    'build_registry_releases_parser',
    'build_registry_reviews_parser',
    'build_registry_skills_parser',
    'build_registry_tokens_parser',
    'configure_registry_parser',
    'registry_main',
]
