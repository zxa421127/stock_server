from __future__ import annotations

from flask import Flask

from routes import admin_member_routes
from services.sync_result import SyncResult


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_member_routes.admin_member_bp, url_prefix="/admin")
    return app


def _login(client, csrf: str = "csrf-token") -> None:
    with client.session_transaction() as session:
        session["admin_logged_in"] = True
        session["admin_csrf_token"] = csrf


def test_member_list_contains_secure_feishu_registration_import_entry(monkeypatch):
    monkeypatch.setattr(admin_member_routes, "list_members", lambda: [])
    client = _app().test_client()
    _login(client)

    response = client.get("/admin/members/list")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'action="/admin/members/import-feishu-registrations"' in body
    assert 'method="post"' in body.lower()
    assert 'name="csrf_token" value="csrf-token"' in body
    assert "导入飞书新登记" in body
    assert "新账号将保持禁用且不会创建Token或套餐" in body
    assert "确认执行吗" in body



def test_member_list_never_embeds_full_api_token(monkeypatch):
    secret = "SK_STOCK_API_FULL_SECRET_SHOULD_NOT_RENDER"
    monkeypatch.setattr(admin_member_routes, "list_members_page", lambda **kwargs: {
        "items": [{
            "user_id": 7, "username": "alice", "user_status": "active",
            "key_status": "active", "token_display": "SK_STOCK_API_…NDER",
        }],
        "total": 1, "page": 1, "page_size": 50, "pages": 1, "query": "",
    })
    client = _app().test_client()
    _login(client)

    body = client.get("/admin/members/list").get_data(as_text=True)

    assert secret not in body
    assert "SK_STOCK_API_…NDER" in body

def test_feishu_registration_import_requires_admin_session(monkeypatch):
    called = []
    monkeypatch.setattr(admin_member_routes, "_run_feishu_registration_import", lambda: called.append(True))

    response = _app().test_client().post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "csrf-token"},
    )

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]
    assert called == []


def test_feishu_registration_import_rejects_invalid_csrf_and_audits(monkeypatch):
    events = []
    called = []
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(admin_member_routes, "_run_feishu_registration_import", lambda: called.append(True))
    client = _app().test_client()
    _login(client, csrf="expected")

    response = client.post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "wrong"},
    )

    assert response.status_code == 400
    assert called == []
    assert "请求校验失败" in response.get_data(as_text=True)
    event = events[-1]
    assert event["action_code"] == "admin.feishu_registration_import"
    assert event["success"] is False
    assert event["error_code"] == "invalid_csrf"


def test_feishu_registration_import_success_shows_counts_and_audits(monkeypatch):
    events = []
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(
        admin_member_routes,
        "_run_feishu_registration_import",
        lambda: SyncResult((2, 3), status="ok", message="飞书登记导入完成"),
    )
    client = _app().test_client()
    _login(client)

    response = client.post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "csrf-token"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "飞书新登记导入完成" in body
    assert "新增本地用户：2" in body
    assert "关联已有用户：3" in body
    assert "新增账号保持禁用且不会创建Token或套餐" in body
    event = events[-1]
    assert event["action_code"] == "admin.feishu_registration_import"
    assert event["success"] is True
    assert event["after_data"] == {"status": "ok", "added_count": 2, "linked_count": 3}
    assert event["request_data"] == {"trigger": "admin_members_page"}


def test_feishu_registration_import_busy_is_safe_and_audited(monkeypatch):
    events = []
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(
        admin_member_routes,
        "_run_feishu_registration_import",
        lambda: SyncResult((0, 0), status="busy", message="飞书同步任务正在运行，当前任务未启动，请稍后重试"),
    )
    client = _app().test_client()
    _login(client)

    response = client.post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "csrf-token"},
    )

    assert response.status_code == 409
    assert "其他飞书同步任务正在运行" in response.get_data(as_text=True)
    assert events[-1]["success"] is False
    assert events[-1]["error_code"] == "busy"


def test_feishu_registration_import_internal_error_hides_sensitive_details(monkeypatch):
    events = []
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(
        admin_member_routes,
        "_run_feishu_registration_import",
        lambda: SyncResult((0, 0), status="error", message="secret-token=SHOULD-NOT-RENDER"),
    )
    client = _app().test_client()
    _login(client)

    response = client.post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "csrf-token"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 500
    assert "导入失败，请查看服务器日志" in body
    assert "SHOULD-NOT-RENDER" not in body
    assert events[-1]["success"] is False
    assert events[-1]["error_code"] == "error"


def test_member_list_import_has_visible_progress_and_json_result(monkeypatch):
    monkeypatch.setattr(admin_member_routes, "list_members", lambda: [])
    monkeypatch.setattr(
        admin_member_routes,
        "_run_feishu_registration_import",
        lambda: SyncResult((3, 19), status="ok", message="飞书登记导入完成"),
    )
    monkeypatch.setattr(
        admin_member_routes,
        "record_operation",
        lambda **kwargs: ("event", True),
    )
    client = _app().test_client()
    _login(client)

    page = client.get("/admin/members/list")
    body = page.get_data(as_text=True)
    assert 'id="feishuRegistrationImportForm"' in body
    assert 'id="feishuImportStatus"' in body
    assert "正在导入" in body
    assert "fetch(form.action" in body
    assert "Accept': 'application/json" in body or 'Accept": "application/json' in body

    response = client.post(
        "/admin/members/import-feishu-registrations",
        data={"csrf_token": "csrf-token"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "success": True,
        "status": "ok",
        "message": "飞书登记导入完成",
        "added_count": 3,
        "linked_count": 19,
    }
