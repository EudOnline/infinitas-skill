import json
import re
from datetime import date
from pathlib import Path

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


def validate_platform_contract(path: Path, expected_title: str) -> tuple[dict, list[str]]:
    path = Path(path)
    errors = []
    payload = {
        'path': path,
        'text': '',
        'urls': [],
        'official_sources': [],
        'last_verified': None,
        'last_verified_raw': '',
    }

    if not path.is_file():
        return payload, [f'{path}: missing platform contract document']

    text = path.read_text(encoding='utf-8')
    payload['text'] = text
    payload['urls'] = URL_RE.findall(text)
    payload['official_sources'] = URL_RE.findall(extract_section(text, '## Official sources'))

    title_line = f'# {expected_title}'
    if title_line not in text:
        errors.append(f'{path}: missing required title {title_line!r}')

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            errors.append(f'{path}: missing required heading {heading!r}')

    last_verified_raw = extract_section(text, '## Last verified')
    payload['last_verified_raw'] = last_verified_raw
    if not last_verified_raw:
        errors.append(f'{path}: missing date value under ## Last verified')
    else:
        match = DATE_RE.search(last_verified_raw)
        if not match:
            errors.append(f'{path}: could not parse Last verified date from {last_verified_raw!r}')
        else:
            try:
                payload['last_verified'] = date.fromisoformat(match.group(1))
            except ValueError:
                errors.append(f'{path}: invalid Last verified date {match.group(1)!r}')

    if not payload['urls']:
        errors.append(f'{path}: must contain at least one HTTPS source URL')

    return payload, errors


def load_platform_profile_contract(path: Path, expected_platform: str) -> tuple[dict, list[str]]:
    path = Path(path)
    errors = []
    payload = {
        'path': path,
        'platform': None,
        'sources': [],
        'last_verified': None,
    }

    if not path.is_file():
        return payload, [f'{path}: missing platform profile JSON']

    try:
        item = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return payload, [f'{path}: invalid JSON: {exc}']

    payload['platform'] = item.get('platform')
    if item.get('platform') != expected_platform:
        errors.append(f'{path}: expected platform {expected_platform!r}, got {item.get("platform")!r}')

    contract = item.get('contract') if isinstance(item.get('contract'), dict) else {}
    sources = contract.get('sources')
    if not isinstance(sources, list) or not sources or not all(isinstance(url, str) and url.startswith('https://') for url in sources):
        errors.append(f'{path}: contract.sources must be a non-empty list of HTTPS URLs')
    else:
        payload['sources'] = list(sources)

    last_verified = contract.get('last_verified')
    if not isinstance(last_verified, str) or not last_verified.strip():
        errors.append(f'{path}: contract.last_verified must be a non-empty string')
    else:
        payload['last_verified'] = last_verified.strip()

    return payload, errors


__all__ = [
    'REQUIRED_HEADINGS',
    'URL_RE',
    'DATE_RE',
    'extract_section',
    'validate_platform_contract',
    'load_platform_profile_contract',
]
