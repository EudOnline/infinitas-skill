#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Hosted registry control plane CLI')
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
    subparsers = parser.add_subparsers(dest='command')

    submissions = subparsers.add_parser('submissions', help='Manage hosted submissions')
    submissions_subparsers = submissions.add_subparsers(dest='subcommand')

    submissions_create = submissions_subparsers.add_parser('create', help='Create a submission')
    submissions_create.add_argument('--skill-name', required=True, help='Skill name to submit')
    submissions_create.add_argument('--publisher', default='local', help='Publisher namespace')
    submissions_create.add_argument('--summary', default='', help='Submission summary')
    submissions_create.add_argument('--payload-json', default='{}', help='JSON payload for the submitted skill metadata')
    submissions_create.set_defaults(func=command_submission_create)

    submissions_validate = submissions_subparsers.add_parser('request-validation', help='Request validation for a submission')
    submissions_validate.add_argument('submission_id', type=int, help='Submission identifier')
    submissions_validate.add_argument('--note', default='', help='Validation note')
    submissions_validate.set_defaults(func=command_submission_request_validation)

    submissions_review = submissions_subparsers.add_parser('request-review', help='Request maintainer review for a submission')
    submissions_review.add_argument('submission_id', type=int, help='Submission identifier')
    submissions_review.add_argument('--note', default='', help='Review request note')
    submissions_review.set_defaults(func=command_submission_request_review)

    reviews = subparsers.add_parser('reviews', help='Review decisions')
    reviews_subparsers = reviews.add_subparsers(dest='subcommand')

    reviews_approve = reviews_subparsers.add_parser('approve', help='Approve a review')
    reviews_approve.add_argument('review_id', type=int, help='Review identifier')
    reviews_approve.add_argument('--note', default='', help='Approval note')
    reviews_approve.set_defaults(func=command_review_approve)

    reviews_reject = reviews_subparsers.add_parser('reject', help='Reject a review')
    reviews_reject.add_argument('review_id', type=int, help='Review identifier')
    reviews_reject.add_argument('--note', default='', help='Rejection note')
    reviews_reject.set_defaults(func=command_review_reject)

    releases = subparsers.add_parser('releases', help='Release queue operations')
    releases_subparsers = releases.add_subparsers(dest='subcommand')

    releases_publish = releases_subparsers.add_parser('publish', help='Queue a publish request for a skill')
    releases_publish.add_argument('skill_name', help='Skill name to publish')
    releases_publish.set_defaults(func=command_release_publish)

    return parser


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


def command_submission_create(args):
    try:
        payload = json.loads(args.payload_json)
    except json.JSONDecodeError as exc:
        fail(f'invalid --payload-json: {exc}')
    return request_json(
        args,
        'POST',
        '/api/v1/submissions',
        {
            'skill_name': args.skill_name,
            'publisher': args.publisher,
            'payload_summary': args.summary,
            'payload': payload,
        },
    )


def command_submission_request_validation(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/submissions/{args.submission_id}/request-validation',
        {'note': args.note},
    )


def command_submission_request_review(args):
    return request_json(
        args,
        'POST',
        f'/api/v1/submissions/{args.submission_id}/request-review',
        {'note': args.note},
    )


def command_review_approve(args):
    return request_json(args, 'POST', f'/api/v1/reviews/{args.review_id}/approve', {'note': args.note})


def command_review_reject(args):
    return request_json(args, 'POST', f'/api/v1/reviews/{args.review_id}/reject', {'note': args.note})


def command_release_publish(args):
    return request_json(args, 'POST', f'/api/v1/skills/{args.skill_name}/publish', {})


def main():
    parser = base_parser()
    args = parser.parse_args()
    func = getattr(args, 'func', None)
    if func is None:
        parser.print_help()
        raise SystemExit(0)
    result = func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
