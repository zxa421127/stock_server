# -*- coding: utf-8 -*-
from pathlib import Path
from unittest.mock import patch

import config
from flask import Flask

from routes import admin_member_routes, user_routes
from services.site_url import admin_url, public_host_from_admin_host, public_url


def test_public_host_derivation_covers_test_production_local_and_custom_prefix():
    assert public_host_from_admin_host("test-admin-api.lifesupermarket.cn") == "test-api.lifesupermarket.cn"
    assert public_host_from_admin_host("admin-api.lifesupermarket.cn") == "api.lifesupermarket.cn"
    assert public_host_from_admin_host("local-admin-api.lifesupermarket.cn") == "local-api.lifesupermarket.cn"
    assert public_host_from_admin_host("staging-admin-api.example.net") == "staging-api.example.net"


def test_cross_domain_urls_follow_existing_admin_host_without_extra_domain_setting():
    cases = [
        ("test-admin-api.lifesupermarket.cn", "https://test-api.lifesupermarket.cn", "https://test-admin-api.lifesupermarket.cn"),
        ("admin-api.lifesupermarket.cn", "https://api.lifesupermarket.cn", "https://admin-api.lifesupermarket.cn"),
        ("local-admin-api.lifesupermarket.cn", "https://local-api.lifesupermarket.cn", "https://local-admin-api.lifesupermarket.cn"),
    ]
    for configured_admin_host, expected_public, expected_admin in cases:
        with patch.object(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", configured_admin_host):
            assert public_url("/user/api-docs") == expected_public + "/user/api-docs"
            assert public_url("user/register") == expected_public + "/user/register"
            assert admin_url("/admin/login") == expected_admin + "/admin/login"


def test_direct_local_development_keeps_relative_links_when_admin_host_is_not_configured():
    with patch.object(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", ""), patch.object(config, "EXPECTED_ADMIN_HOST", ""):
        assert public_url("/user/login") == "/user/login"
        assert admin_url("/admin/login") == "/admin/login"


def test_admin_member_navigation_and_login_use_public_domain():
    with patch.object(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "test-admin-api.lifesupermarket.cn"):
        nav = admin_member_routes._admin_nav()
        login = admin_member_routes._admin_login_form()

    assert 'href="https://test-api.lifesupermarket.cn/user/register"' in nav
    assert 'href="https://test-api.lifesupermarket.cn/user/login"' in login
    assert 'href="https://test-api.lifesupermarket.cn/user/register"' in login
    assert 'href="/user/' not in nav
    assert 'href="/user/' not in login


def test_user_pages_use_admin_domain_for_admin_links(monkeypatch):
    with patch.object(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "test-admin-api.lifesupermarket.cn"):
        page = user_routes._page("test", "<p>body</p>")
        assert 'href="https://test-admin-api.lifesupermarket.cn/admin/login"' in page

        monkeypatch.setattr(user_routes, "list_public_docs", lambda: [])
        monkeypatch.setattr(user_routes, "get_api_doc_statistics", lambda public_only=True: {})
        app = Flask(__name__)
        app.secret_key = "test-secret"
        app.register_blueprint(user_routes.user_bp, url_prefix="/user")
        response = app.test_client().get("/user/api-docs")
        html = response.get_data(as_text=True)
        assert 'href="https://test-admin-api.lifesupermarket.cn/admin/api-docs"' in html


def test_no_cross_domain_relative_links_remain_in_route_sources():
    root = Path(__file__).resolve().parents[1]
    admin_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "routes").glob("admin_*.py"))
    )
    user_source = (root / "routes" / "user_routes.py").read_text(encoding="utf-8")

    assert 'href="/user/' not in admin_sources
    assert "href='/user/" not in admin_sources
    assert 'href="/admin/' not in user_source
    assert "href='/admin/" not in user_source
