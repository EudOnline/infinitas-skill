from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request


def pick_lang(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


def with_lang(href: str, lang: str) -> str:
    if not href or href.startswith("#"):
        return href
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return href
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["lang"] = lang
    return urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))


def resolve_language(request: Request) -> str:
    lang = (request.query_params.get("lang") or "zh").strip().lower()
    return "en" if lang.startswith("en") else "zh"


def request_path_with_query(request: Request) -> str:
    path = request.url.path or "/"
    query = request.url.query
    if query:
        return f"{path}?{query}"
    return path


def build_auth_redirect_url(request: Request, lang: str) -> str:
    target_parts = urlsplit(with_lang("/", lang))
    query = dict(parse_qsl(target_parts.query, keep_blank_values=True))
    query["auth"] = "required"
    query["next"] = request_path_with_query(request)
    return urlunsplit(("", "", target_parts.path or "/", urlencode(query), target_parts.fragment))


def build_language_switches(request: Request, lang: str) -> list[dict[str, str | bool]]:
    return [
        {
            "code": code,
            "label": label,
            "href": str(request.url.include_query_params(lang=code)),
            "active": code == lang,
        }
        for code, label in (("zh", "中"), ("en", "EN"))
    ]


__all__ = [
    "build_auth_redirect_url",
    "build_language_switches",
    "pick_lang",
    "request_path_with_query",
    "resolve_language",
    "with_lang",
]
