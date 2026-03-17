#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from review_evidence_lib import ReviewEvidenceError, load_review_evidence, review_evidence_path
from review_lib import resolve_skill

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_args():
    parser = argparse.ArgumentParser(description='Import normalized platform review evidence for one skill')
    parser.add_argument('skill')
    parser.add_argument('--input', required=True, help='Path to a normalized review-evidence JSON payload')
    parser.add_argument('--json', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    skill_dir = resolve_skill(ROOT, args.skill)
    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        fail(f'missing input file: {input_path}')

    try:
        payload = json.loads(input_path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'invalid JSON in input file {input_path}: {exc}')

    target_path = review_evidence_path(skill_dir)
    previous = target_path.read_text(encoding='utf-8') if target_path.exists() else None
    write_json(target_path, payload)
    try:
        evidence = load_review_evidence(skill_dir)
    except ReviewEvidenceError as exc:
        if previous is None:
            target_path.unlink(missing_ok=True)
        else:
            target_path.write_text(previous, encoding='utf-8')
        fail(str(exc))

    result = {
        'skill': str(skill_dir.relative_to(ROOT)),
        'review_evidence_path': str(target_path.relative_to(ROOT)),
        'imported_count': len(evidence.get('entries', [])),
        'reviewers': [item.get('reviewer') for item in evidence.get('entries', [])],
        'sources': sorted({item.get('source_kind') for item in evidence.get('entries', []) if item.get('source_kind')}),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result['review_evidence_path'])


if __name__ == '__main__':
    main()
