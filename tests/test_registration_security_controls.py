from services import captcha_service
from services.web_security import AttemptLimiter


def test_attempt_limiter_counts_every_allowed_attempt_and_then_blocks():
    now = [100.0]
    limiter = AttemptLimiter(
        max_attempts=2,
        window_seconds=60,
        lock_seconds=120,
        clock=lambda: now[0],
        redis_getter=lambda: None,
        namespace="registration-ip",
        require_redis=False,
    )
    assert limiter.check_and_record("1.2.3.4") is True
    assert limiter.check_and_record("1.2.3.4") is True
    assert limiter.check_and_record("1.2.3.4") is False
    now[0] += 121
    assert limiter.check_and_record("1.2.3.4") is True


def test_attempt_limiter_fails_closed_when_shared_backend_required():
    limiter = AttemptLimiter(
        max_attempts=5,
        window_seconds=60,
        lock_seconds=60,
        redis_getter=lambda: None,
        namespace="registration-global",
        require_redis=True,
    )
    assert limiter.check_and_record("global") is False


def test_generic_captcha_is_namespaced_hashed_expiring_and_single_use(monkeypatch):
    session = {}
    monkeypatch.setattr(captcha_service.config, "SECRET_KEY", "s" * 64)
    monkeypatch.setattr(captcha_service.secrets, "choice", lambda alphabet: alphabet[0])

    admin_code = captcha_service.issue_captcha(session, "admin", length=5, now=1000)
    registration_code = captcha_service.issue_captcha(session, "registration", length=5, now=1000)

    assert admin_code not in repr(session)
    assert registration_code not in repr(session)
    assert captcha_service.session_key("admin") != captcha_service.session_key("registration")
    assert captcha_service.verify_captcha(session, "admin", admin_code, now=1001, ttl_seconds=300)
    assert not captcha_service.verify_captcha(session, "admin", admin_code, now=1002, ttl_seconds=300)
    assert captcha_service.verify_captcha(session, "registration", registration_code, now=1001, ttl_seconds=300)


def test_generic_captcha_consumes_invalid_and_expired_challenges(monkeypatch):
    session = {}
    monkeypatch.setattr(captcha_service.config, "SECRET_KEY", "s" * 64)
    monkeypatch.setattr(captcha_service.secrets, "choice", lambda alphabet: alphabet[0])
    code = captcha_service.issue_captcha(session, "registration", length=5, now=1000)
    assert not captcha_service.verify_captcha(session, "registration", "wrong", now=1001, ttl_seconds=300)
    assert not captcha_service.verify_captcha(session, "registration", code, now=1002, ttl_seconds=300)

    code = captcha_service.issue_captcha(session, "registration", length=5, now=1000)
    assert not captcha_service.verify_captcha(session, "registration", code, now=1301, ttl_seconds=300)
    assert captcha_service.session_key("registration") not in session
