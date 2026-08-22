from __future__ import annotations

import time

from services import admin_captcha


class SessionDict(dict):
    modified = False


def test_captcha_is_stored_as_hash_and_is_single_use(monkeypatch):
    session = SessionDict()
    monkeypatch.setattr(admin_captcha.config, "SECRET_KEY", "s" * 64)
    monkeypatch.setattr(admin_captcha.secrets, "choice", lambda alphabet: alphabet[0])

    code = admin_captcha.issue_admin_captcha(session, length=5, now=1000)

    assert code == admin_captcha.CAPTCHA_ALPHABET[0] * 5
    state = session[admin_captcha.SESSION_KEY]
    assert code not in str(state)
    assert state["digest"]
    assert admin_captcha.verify_admin_captcha(session, code, now=1001, ttl_seconds=300)
    assert admin_captcha.SESSION_KEY not in session
    assert not admin_captcha.verify_admin_captcha(session, code, now=1002, ttl_seconds=300)


def test_refresh_invalidates_previous_code(monkeypatch):
    session = SessionDict()
    monkeypatch.setattr(admin_captcha.config, "SECRET_KEY", "s" * 64)
    values = iter(["A"] * 5 + ["B"] * 5)
    monkeypatch.setattr(admin_captcha.secrets, "choice", lambda alphabet: next(values))

    first = admin_captcha.issue_admin_captcha(session, length=5, now=1000)
    second = admin_captcha.issue_admin_captcha(session, length=5, now=1001)

    assert first == "AAAAA"
    assert second == "BBBBB"
    assert not admin_captcha.verify_admin_captcha(session, first, now=1002, ttl_seconds=300)


def test_captcha_expires_and_comparison_is_case_sensitive(monkeypatch):
    session = SessionDict()
    monkeypatch.setattr(admin_captcha.config, "SECRET_KEY", "s" * 64)
    values = iter("aB3Cd")
    monkeypatch.setattr(admin_captcha.secrets, "choice", lambda alphabet: next(values))
    code = admin_captcha.issue_admin_captcha(session, length=5, now=1000)

    assert not admin_captcha.verify_admin_captcha(session, code.swapcase(), now=1001, ttl_seconds=300)

    values = iter("aB3Cd")
    monkeypatch.setattr(admin_captcha.secrets, "choice", lambda alphabet: next(values))
    admin_captcha.issue_admin_captcha(session, length=5, now=1000)
    assert not admin_captcha.verify_admin_captcha(session, code, now=1301, ttl_seconds=300)


def test_rendered_captcha_is_png():
    data = admin_captcha.render_admin_captcha_png("aB3Cd", width=180, height=58)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data) > 500
