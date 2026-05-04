from __future__ import annotations

from server.auth import (
    _decode_auth_session_cookie,
    _extract_bearer_token,
    _session_signature,
    _urlsafe_b64decode,
    _urlsafe_b64encode,
    create_auth_session_cookie,
    generate_csrf_token,
)


class TestExtractBearerToken:
    def test_valid_bearer(self):
        assert _extract_bearer_token("Bearer my-token") == "my-token"

    def test_no_bearer_prefix(self):
        assert _extract_bearer_token("my-token") is None

    def test_none_input(self):
        assert _extract_bearer_token(None) is None

    def test_empty_string(self):
        assert _extract_bearer_token("") is None

    def test_lowercase_bearer(self):
        assert _extract_bearer_token("bearer my-token") is None


class TestUrlsafeB64:
    def test_encode_decode_roundtrip(self):
        raw = b"hello world"
        encoded = _urlsafe_b64encode(raw)
        decoded = _urlsafe_b64decode(encoded)
        assert decoded == raw


class TestSessionSignature:
    def test_signature_is_deterministic(self):
        sig1 = _session_signature('{"test": true}')
        sig2 = _session_signature('{"test": true}')
        assert sig1 == sig2

    def test_different_payloads_different_signatures(self):
        sig1 = _session_signature('{"a": 1}')
        sig2 = _session_signature('{"a": 2}')
        assert sig1 != sig2


class TestCreateAuthSessionCookie:
    def test_cookie_starts_with_prefix(self):
        cookie = create_auth_session_cookie(42)
        assert cookie.startswith("session:")

    def test_cookie_is_urlsafe(self):
        cookie = create_auth_session_cookie(1)
        assert " " not in cookie
        assert "+" not in cookie
        assert "/" not in cookie


class TestDecodeAuthSessionCookie:
    def test_roundtrip(self):
        cookie = create_auth_session_cookie(99)
        decoded = _decode_auth_session_cookie(cookie)
        assert decoded is not None
        assert decoded["credential_id"] == 99

    def test_invalid_cookie_returns_none(self):
        assert _decode_auth_session_cookie("not-a-valid-cookie") is None

    def test_none_input_returns_none(self):
        assert _decode_auth_session_cookie(None) is None

    def test_tampered_cookie_returns_none(self):
        cookie = create_auth_session_cookie(1)
        tampered = cookie + "x"
        assert _decode_auth_session_cookie(tampered) is None


class TestGenerateCsrfToken:
    def test_token_is_urlsafe(self):
        token = generate_csrf_token()
        assert "+" not in token
        assert "/" not in token
        assert "=" not in token

    def test_tokens_are_unique(self):
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert token1 != token2

    def test_token_is_nonempty(self):
        assert len(generate_csrf_token()) > 0
