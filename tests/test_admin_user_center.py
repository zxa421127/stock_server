from __future__ import annotations

from flask import Flask

from routes import admin_member_routes, admin_user_routes
from services.admin_user_service import UserProfileConflictError


def _detail(status="active"):
    return {
        "user": {
            "id": 7,
            "username": "alice",
            "phone": "13800138000",
            "email": "alice@example.com",
            "taobao_nick": "Alice淘宝",
            "register_source": "self",
            "status": status,
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-02 10:00:00",
            "last_login_at": "2026-07-20 09:00:00",
        },
        "current_subscription": {
            "plan_code": "general_month",
            "start_time": "2026-07-01 00:00:00",
            "expire_time": "2026-08-01 00:00:00",
        },
        "scheduled_subscriptions": [],
        "token_summary": {"total": 2, "active": 1, "disabled": 1},
    }


def _history_result(items=None):
    return {
        "items": items or [], "total": len(items or []), "page": 1, "page_size": 20, "pages": 1,
        "stats": {"total": len(items or []), "success_count": 0, "failure_count": 0, "target_user_count": 1, "admin_count": 0, "user_count": 0},
    }


def _app(monkeypatch):
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail())
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda *args, **kwargs: _history_result())
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    return app


def _login(client, csrf="csrf-token"):
    with client.session_transaction() as session:
        session["admin_logged_in"] = True
        session["admin_csrf_token"] = csrf


def test_detail_page_requires_admin_session(monkeypatch):
    client = _app(monkeypatch).test_client()
    response = client.get("/admin/users/7")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_detail_page_shows_editable_profile_status_summary_and_histories(monkeypatch):
    auth_item = {
        "created_at": "2026-07-20 09:00:00", "success": True,
        "action_name": "用户登录成功", "action_code": "user.auth.login_success",
        "client_ip": "127.0.0.1", "user_agent": "pytest", "error_message": "",
    }
    admin_item = {
        "created_at": "2026-07-20 10:00:00", "success": True,
        "action_name": "修改用户资料", "action_code": "admin.user_profile.update",
        "client_ip": "127.0.0.1", "user_agent": "pytest", "error_message": "",
    }
    calls = []
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail())
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda filters, *args, **kwargs: calls.append(filters) or _history_result([auth_item] if filters.get("action_category") == "authentication" else [admin_item]))
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)

    response = client.get("/admin/users/7")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "用户编辑中心" in body
    assert "alice" in body
    assert 'name="phone"' in body and 'name="email"' in body
    assert 'name="taobao_nick"' in body and 'name="register_source"' in body
    assert "用户自助注册" in body
    assert "general_month" in body
    assert "Token总数" in body and "2" in body
    assert "登录/退出记录" in body and "管理员操作记录" in body
    assert "用户登录成功" in body and "修改用户资料" in body
    assert "target_user_id=7" in body
    assert {call.get("target_user_id") for call in calls} == {7}


def test_member_list_contains_view_edit_link(monkeypatch):
    monkeypatch.setattr(admin_member_routes, "list_members_page", lambda **kwargs: {
        "items": [{
            "user_id": 7, "username": "alice", "phone": "13800138000", "email": "alice@example.com",
            "taobao_nick": "", "register_source": "self", "user_status": "active", "key_status": "active",
            "token_display": "SK_STOCK_API_…OKEN", "plan_code": None, "scheduled_plan_code": None,
        }],
        "total": 1, "page": 1, "page_size": 50, "pages": 1, "query": "",
    })
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_member_routes.admin_member_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)
    body = client.get("/admin/members/list").get_data(as_text=True)
    assert '/admin/users/7' in body
    assert "查看/编辑" in body


def test_profile_update_checks_csrf_and_records_local_and_feishu_audits(monkeypatch):
    events = []
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail())
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda *a, **k: _history_result())
    monkeypatch.setattr(admin_user_routes, "update_user_profile", lambda user_id, payload: {
        "user": _detail()["user"] | {"email": "new@example.com"},
        "before": {"phone": "13800138000", "email": "alice@example.com"},
        "after": {"phone": "13800138000", "email": "new@example.com"},
        "changed_fields": ["email"],
    })
    monkeypatch.setattr(admin_user_routes, "sync_user_profile_to_feishu", lambda user_id: {"status": "success", "result": "updated", "error": ""})
    monkeypatch.setattr(admin_user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)

    denied = client.post("/admin/users/7", data={"csrf_token": "wrong"})
    assert denied.status_code == 403
    assert events[-1]["error_code"] == "csrf_invalid"
    events.clear()

    response = client.post("/admin/users/7", data={
        "csrf_token": "csrf-token", "phone": "13800138000", "email": "new@example.com",
        "taobao_nick": "Alice淘宝", "register_source": "self",
    })
    assert response.status_code == 302
    assert events[0]["action_code"] == "admin.user_profile.update"
    assert events[0]["before_data"]["email"] == "alice@example.com"
    assert events[1]["action_code"] == "admin.user_profile.feishu_sync"
    assert events[1]["success"] is True


def test_profile_update_conflict_renders_error_and_audits_failure(monkeypatch):
    events = []
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail())
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda *a, **k: _history_result())
    monkeypatch.setattr(admin_user_routes, "update_user_profile", lambda *a, **k: (_ for _ in ()).throw(UserProfileConflictError("邮箱已被使用", "duplicate_email")))
    monkeypatch.setattr(admin_user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)

    response = client.post("/admin/users/7", data={
        "csrf_token": "csrf-token", "phone": "13800138000", "email": "used@example.com",
        "taobao_nick": "", "register_source": "self",
    })
    assert response.status_code == 409
    assert "邮箱已被使用" in response.get_data(as_text=True)
    assert events[-1]["success"] is False
    assert events[-1]["error_code"] == "duplicate_email"


def test_status_change_requires_csrf_and_does_not_touch_tokens_in_route(monkeypatch):
    events = []
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail("disabled"))
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda *a, **k: _history_result())
    monkeypatch.setattr(admin_user_routes, "set_user_status", lambda user_id, status: {
        "user": _detail(status)["user"],
        "before": {"status": "active"}, "after": {"status": status}, "changed": True,
    })
    monkeypatch.setattr(admin_user_routes, "sync_user_profile_to_feishu", lambda user_id: {"status": "disabled", "result": "", "error": ""})
    monkeypatch.setattr(admin_user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)

    response = client.post("/admin/users/7/status", data={"csrf_token": "csrf-token", "status": "disabled"})
    assert response.status_code == 302
    assert events[0]["action_code"] == "admin.user_status.disable"
    assert events[0]["after_data"]["status"] == "disabled"


def test_feishu_failure_keeps_local_change_and_renders_warning_notice(monkeypatch):
    events = []
    monkeypatch.setattr(admin_user_routes, "get_admin_user_detail", lambda user_id: _detail())
    monkeypatch.setattr(admin_user_routes, "query_operation_logs", lambda *a, **k: _history_result())
    monkeypatch.setattr(admin_user_routes, "update_user_profile", lambda user_id, payload: {
        "user": _detail()["user"], "before": {"email": "old@example.com"},
        "after": {"email": "new@example.com"}, "changed_fields": ["email"],
    })
    monkeypatch.setattr(admin_user_routes, "sync_user_profile_to_feishu", lambda user_id: {"status": "failed", "result": "", "error": "network down"})
    monkeypatch.setattr(admin_user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_user_routes.admin_user_bp, url_prefix="/admin")
    client = app.test_client()
    _login(client)

    response = client.post("/admin/users/7", data={
        "csrf_token": "csrf-token", "phone": "13800138000", "email": "new@example.com",
        "taobao_nick": "Alice淘宝", "register_source": "self",
    }, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'class="notice warning"' in body
    assert "本地资料已修改，但飞书同步失败" in body
    assert events[-1]["success"] is False
    assert events[-1]["error_code"] == "feishu_sync_failed"
