#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = {
    'claude': 'Claude Platform Contract',
    'codex': 'Codex Platform Contract',
    'openclaw': 'OpenClaw Platform Contract',
}
REQUIRED_HEADINGS = [
    '## Stable assumptions',
    '## Volatile assumptions',
    '## Official sources',
    '## Last verified',
    '## Verification steps',
    '## Known gaps',
]
URL_RE = re.compile(r'https://\S+')
DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)


def warn(message):
    print(f'WARN: {message}', file=sys.stderr)


def extract_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    capture = False
    collected = []
    for line in lines:
        if line.strip() == heading:
            capture = True
            continue
        if capture and line.startswith('## '):
            break
        if capture:
            collected.append(line)
    return '\n'.join(collected).strip()


def parse_verified_date(text: str, *, path: Path) -> date | None:
    section = extract_section(text, '## Last verified')
    if not section:
        fail(f'{path}: missing date value under ## Last verified')
        return None
    match = DATE_RE.search(section)
    if not match:
        fail(f'{path}: could not parse Last verified date from {section!r}')
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        fail(f'{path}: invalid Last verified date {match.group(1)!r}')
        return None


def check_doc(path: Path, title: str, *, max_age_days: int | None) -> tuple[int, int]:
    errors = 0
    warnings = 0
    if not path.is_file():
        fail(f'{path}: missing platform contract document')
        return 1, 0

    text = path.read_text(encoding='utf-8')
    expected_title = f'# {title}'
    if expected_title not in text:
        fail(f'{path}: missing required title {expected_title!r}')
        errors += 1

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            fail(f'{path}: missing required heading {heading!r}')
            errors += 1

    verified_date = parse_verified_date(text, path=path)
    if verified_date is None:
        errors += 1
    elif max_age_days is not None:
        age_days = (date.today() - verified_date).days
        if age_days > max_age_days:
            warn(f'{path}: last verified {verified_date.isoformat()} is {age_days} days old (threshold {max_age_days})')
            warnings += 1

    urls = URL_RE.findall(text)
    if not urls:
        fail(f'{path}: must contain at least one HTTPS source URL')
        errors += 1

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Check platform contract-watch documents.')
    parser.add_argument('--max-age-days', type=int, default=None, help='Warn when Last verified is older than this many days.')
    args = parser.parse_args()

    errors = 0
    warnings = 0
    for slug, title in REQUIRED_DOCS.items():
        doc_path = ROOT / 'docs' / 'platform-contracts' / f'{slug}.md'
        doc_errors, doc_warnings = check_doc(doc_path, title, max_age_days=args.max_age_days)
        errors += doc_errors
        warnings += doc_warnings

    if errors:
        return 1
    print(f'OK: verified {len(REQUIRED_DOCS)} platform contract document(s) ({warnings} warning(s))')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
