from __future__ import annotations

import pytest

import app as app_module
import config
from routes import admin_member_routes
from services.web_security import LoginAttemptLimiter


@pytest.fixture
def hardened_app(monkeypatch):
    monkeypatch.setattr(app_module, "init_db", lambda: None)
    monkeypatch.setattr(app_module, "begin_api_audit", lambda: None)
    monkeypatch.setattr(app_module, "finish_api_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "close_thread_connection", lambda: None)
    monkeypatch.setattr(config, "APP_ENV", "development")
    monkeypatch.setattr(config, "DEPLOYMENT_SLOT", "", raising=False)
    monkeypatch.setattr(config, "ENVIRONMENT_GUARD_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "EXPECTED_ADMIN_HOST", "", raising=False)
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "", raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_REQUIRED", False, raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "", raising=False)
    monkeypatch.setattr(config, "SECRET_KEY", "s" * 64)
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "strong-admin-password")
    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(config, "ADMIN_IP_WHITELIST", [])
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://trusted.example"])
    monkeypatch.setattr(admin_member_routes, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(admin_member_routes, "ADMIN_PASSWORD", "strong-admin-password")
    monkeypatch.setattr(admin_member_routes, "ADMIN_IP_WHITELIST", [])
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: ("event", True))
    monkeypatch.setattr(admin_member_routes, "verify_admin_captcha", lambda session_obj, supplied: supplied == "aB3Cd")
    monkeypatch.setattr(
        admin_member_routes,
        "_admin_login_limiter",
        LoginAttemptLimiter(
            max_failures=5,
            window_seconds=60,
            lock_seconds=120,
            redis_getter=lambda: None,
            namespace="admin-test",
            require_redis=False,
        ),
    )
    app = app_module.create_app(start_background=False, configure_logging=False)
    app.config.update(TESTING=True)
    return app



def test_admin_user_center_blueprint_is_registered(hardened_app):
    rules = {rule.rule for rule in hardened_app.url_map.iter_rules()}
    assert "/admin/users/<int:user_id>" in rules
    assert "/admin/users/<int:user_id>/status" in rules

def test_forged_forwarded_for_cannot_bypass_admin_whitelist(hardened_app, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IP_WHITELIST", ["8.8.8.8"])
    monkeypatch.setattr(admin_member_routes, "ADMIN_IP_WHITELIST", ["8.8.8.8"])
    response = hardened_app.test_client().get(
        "/admin/login",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert response.status_code == 403


def test_admin_logout_requires_post_and_csrf(hardened_app):
    client = hardened_app.test_client()
    login = client.post("/admin/login", data={"username": "admin", "password": "strong-admin-password", "captcha": "aB3Cd"})
    assert login.status_code == 302
    with client.session_transaction() as sess:
        csrf = sess["admin_csrf_token"]

    assert client.get("/admin/logout").status_code == 405
    assert client.post("/admin/logout").status_code == 403
    assert client.post("/admin/logout", headers={"X-CSRF-Token": csrf}).status_code == 302


def test_security_headers_cors_and_secure_cookie(hardened_app):
    response = hardened_app.test_client().get(
        "/ping",
        base_url="https://service.example",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self' 'nonce-" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ", 1)[1].split(";", 1)[0]
    assert "script-src-attr 'unsafe-inline'" not in csp
    assert response.headers["Permissions-Policy"].startswith("camera=()")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_admin_login_rate_limit_returns_429(hardened_app, monkeypatch):
    limiter = LoginAttemptLimiter(
        max_failures=2,
        window_seconds=60,
        lock_seconds=120,
        redis_getter=lambda: None,
        namespace="admin-rate-limit-test",
        require_redis=False,
    )
    monkeypatch.setattr(admin_member_routes, "_admin_login_limiter", limiter)
    client = hardened_app.test_client()
    data = {"username": "admin", "password": "wrong", "captcha": "aB3Cd"}
    assert client.post("/admin/login", data=data).status_code == 401
    assert client.post("/admin/login", data=data).status_code == 401
    assert client.post("/admin/login", data=data).status_code == 429


def test_internal_error_response_does_not_leak_exception_details(hardened_app):
    @hardened_app.get("/_test_error")
    def _test_error():
        raise RuntimeError("SECRET_SENTINEL")

    response = hardened_app.test_client().get("/_test_error")
    assert response.status_code == 500
    assert "SECRET_SENTINEL" not in response.get_data(as_text=True)
    assert "服务器内部异常" in str(response.get_json().get("msg"))


def test_create_app_without_background_does_not_start_workers(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "init_db", lambda: None)
    monkeypatch.setattr(config, "APP_ENV", "development")
    monkeypatch.setattr(config, "SECRET_KEY", "s" * 64)
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "strong-admin-password")
    monkeypatch.setattr(app_module, "start_runtime_services", lambda: calls.append("started"))
    app_module.create_app(start_background=False, configure_logging=False)
    assert calls == []


def test_html_sources_do_not_use_inline_event_attributes():
    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1]
    patterns = re.compile(r"<[^>]+\bon(?:click|change|submit|input|load|error)\s*=", re.IGNORECASE)
    findings = []
    for folder in (root / "routes", root / "templates"):
        for path in folder.rglob("*"):
            if path.suffix not in {".py", ".html"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if patterns.search(text):
                findings.append(str(path.relative_to(root)))
    assert findings == []


def test_external_admin_request_without_proxy_certificate_headers_is_rejected(hardened_app):
    response = hardened_app.test_client().get(
        "/admin/login",
        base_url="https://admin-api.example.com",
        environ_overrides={"REMOTE_ADDR": "203.0.113.10"},
    )
    assert response.status_code == 403
    assert "管理员客户端证书验证失败" in response.get_data(as_text=True)

def test_user_api_key_rotate_requires_global_csrf(hardened_app):
    client = hardened_app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 7
        session["user_session_version"] = 1
        session["user_csrf_token"] = "known-csrf"

    response = client.post(
        "/user/api-key/rotate",
        data={"password": "not-reached"},
    )

    assert response.status_code == 403

def test_csp_style_src_excludes_unsafe_inline(hardened_app):
    response = hardened_app.test_client().get(
        '/ping',
        base_url='https://service.example',
    )
    assert response.status_code == 200
    csp = response.headers['Content-Security-Policy']
    directives = [
        item.strip()
        for item in csp.split(';')
        if item.strip()
    ]
    style_src = [
        item
        for item in directives
        if item.startswith('style-src ')
    ]
    assert len(style_src) == 1
    tokens = style_src[0].split()[1:]
    assert "'self'" in tokens
    assert "'unsafe-inline'" not in tokens


def test_csp_inline_style_migration_source_contract():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source_files = ['app.py', 'routes/admin_api_doc_routes.py', 'routes/admin_audit_routes.py', 'routes/admin_member_routes.py', 'routes/admin_user_routes.py', 'routes/user_routes.py', 'templates/admin/interface_tester.html']
    for relative in source_files:
        text = (root / relative).read_text(encoding='utf-8-sig')
        assert re.search(r'\bstyle\s*=', text, flags=re.IGNORECASE) is None
        assert re.search(r'<style\b', text, flags=re.IGNORECASE) is None

    app_text = (root / 'app.py').read_text(encoding='utf-8-sig')
    assert "style-src 'self' 'unsafe-inline'" not in app_text
    assert "style-src 'self';" in app_text
    assert '/static/csp/r5-inline-attributes.css' in app_text

    css_assets = ['static/csp/r5-inline-attributes.css', 'static/csp/r5-routes-admin-api-doc-routes-l82-0cb552468e.css', 'static/csp/r5-routes-admin-audit-routes-l77-a92cad9dfd.css', 'static/csp/r5-routes-admin-member-routes-l173-9f62b2453c.css', 'static/csp/r5-routes-admin-user-routes-l180-622868a952.css', 'static/csp/r5-routes-user-routes-l1271-8ca4484eec.css', 'static/csp/r5-routes-user-routes-l131-7bfed51700.css', 'static/csp/r5-templates-admin-interface-tester-l7-e49d9ef370.css']
    assert len(css_assets) == 8
    for relative in css_assets:
        path = root / relative
        assert path.is_file()
        assert path.read_text(encoding='utf-8').strip()
