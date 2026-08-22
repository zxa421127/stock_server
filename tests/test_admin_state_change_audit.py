from __future__ import annotations

from flask import Flask

from middleware import auth
from routes import admin_api_doc_routes, admin_sync_routes, market_data_routes


def _authorize_admin_scope(monkeypatch):
    context = {
        "user": {"id": 3, "username": "ops", "phone": "13812345678", "email": "ops@example.com"},
        "subscription": {"plan_code": "special_year"},
        "plan": {"plan_code": "special_year", "scopes": '["admin:sync"]'},
        "scopes": ["admin:sync"],
    }
    monkeypatch.setattr(auth, "resolve_auth_context", lambda token: context)
    monkeypatch.setattr(auth, "scope_allowed", lambda *args: True)
    monkeypatch.setattr(auth, "check_rate_limit", lambda *args: (True, ""))
    monkeypatch.setattr(auth, "enqueue_api_key_touch", lambda *args: None)
    monkeypatch.setattr(auth, "enqueue_usage_log", lambda **kwargs: None)
    monkeypatch.setattr(auth, "mark_api_auth_state", lambda *args, **kwargs: None)


def test_admin_sync_and_cache_clear_record_success(monkeypatch):
    _authorize_admin_scope(monkeypatch)
    events = []
    monkeypatch.setattr(admin_sync_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True), raising=False)
    monkeypatch.setattr(market_data_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True), raising=False)
    monkeypatch.setattr(admin_sync_routes.config, "ENABLE_FEISHU_SYNC", True)
    import services.feishu_sync_service as feishu
    monkeypatch.setattr(feishu, "trigger_sync_now", lambda: None)
    monkeypatch.setattr(market_data_routes, "clear_cache", lambda: None)
    monkeypatch.setattr(market_data_routes, "cache_stats", lambda: {"entries": 0})

    app = Flask(__name__)
    app.register_blueprint(admin_sync_routes.admin_sync_bp, url_prefix="/api/admin")
    app.register_blueprint(market_data_routes.market_data_bp, url_prefix="/api/v1/market")
    client = app.test_client()

    response = client.post("/api/admin/sync/feishu", headers={"X-API-Token": "x"})
    assert response.status_code == 200
    assert response.get_json()["msg"] == "已触发本地→飞书同步"
    assert events[-1]["action_code"] == "admin.feishu_sync"
    assert events[-1]["success"] is True

    assert client.post("/api/v1/market/cache/clear", headers={"X-API-Token": "x"}).status_code == 200
    assert events[-1]["action_code"] == "admin.cache_clear"
    assert events[-1]["actor_id"] == 3


def test_disabled_admin_sync_records_failure(monkeypatch):
    _authorize_admin_scope(monkeypatch)
    events = []
    monkeypatch.setattr(admin_sync_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True), raising=False)
    monkeypatch.setattr(admin_sync_routes.config, "ENABLE_FEISHU_SYNC", False)
    app = Flask(__name__)
    app.register_blueprint(admin_sync_routes.admin_sync_bp, url_prefix="/api/admin")

    response = app.test_client().post("/api/admin/sync/feishu", headers={"X-API-Token": "x"})
    assert response.status_code == 503
    assert events[-1]["action_code"] == "admin.feishu_sync"
    assert events[-1]["success"] is False


def test_api_doc_create_success_and_failure_are_audited(monkeypatch):
    events = []
    monkeypatch.setattr(admin_api_doc_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True), raising=False)
    monkeypatch.setattr(admin_api_doc_routes, "create_category", lambda **kwargs: 11)
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_api_doc_routes.admin_api_doc_bp, url_prefix="/admin")
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post("/admin/api-docs/categories/new", data={"name": "竞价", "sort_order": "100", "status": "active"})
    assert response.status_code == 302
    assert events[-1]["action_code"] == "admin.api_doc_category_create"
    assert events[-1]["success"] is True

    monkeypatch.setattr(admin_api_doc_routes, "create_category", lambda **kwargs: (_ for _ in ()).throw(ValueError("bad category")))
    response = client.post("/admin/api-docs/categories/new", data={"name": "", "sort_order": "100"})
    assert response.status_code == 400
    assert events[-1]["success"] is False
    assert events[-1]["error_message"] == "bad category"
