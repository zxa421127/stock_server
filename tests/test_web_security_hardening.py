# -*- coding: utf-8 -*-
from flask import Flask
from services.web_security import LoginAttemptLimiter, client_ip


def test_client_ip_ignores_untrusted_x_forwarded_for():
    app=Flask(__name__)
    with app.test_request_context('/', environ_base={'REMOTE_ADDR':'127.0.0.1'}, headers={'X-Forwarded-For':'8.8.8.8'}):
        assert client_ip() == '127.0.0.1'


def test_login_limiter_blocks_after_threshold_and_can_clear():
    now=[1000.0]
    limiter=LoginAttemptLimiter(max_failures=3, window_seconds=60, lock_seconds=120, clock=lambda:now[0])
    assert not limiter.is_blocked('ip')
    limiter.record_failure('ip'); limiter.record_failure('ip'); limiter.record_failure('ip')
    assert limiter.is_blocked('ip')
    limiter.clear('ip')
    assert not limiter.is_blocked('ip')
