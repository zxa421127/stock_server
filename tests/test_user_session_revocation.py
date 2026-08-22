from __future__ import annotations

from flask import Flask, session

import config
import db_utils
from routes import user_routes
from services import member_service
from services.admin_user_service import set_user_status


def _use_database(monkeypatch, path):
    db_utils.close_thread_connection()
    monkeypatch.setattr(db_utils, "DB_FILE", str(path))
    monkeypatch.setattr(db_utils, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "APP_ENV", "test")
    db_utils._db_pragmas_initialized = False
    db_utils.init_db()


def _create_user(username="alice"):
    conn = db_utils.get_conn()
    now = "2026-07-26 10:00:00"
    conn.execute(
        "INSERT INTO users(username,email,password_hash,status,session_version,registration_status,created_at,updated_at) "
        "VALUES (?,?,?,'active',1,'active',?,?)",
        (username, f"{username}@example.com", member_service.hash_password("Old password 123!"), now, now),
    )
    conn.commit()
    return db_utils.get_user_by_account(username)


def _app():
    app = Flask(__name__)
    app.secret_key = "test-secret-" * 8
    app.register_blueprint(user_routes.user_bp, url_prefix="/user")
    return app


def test_current_user_rejects_mismatched_session_version(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "session.db")
    user = _create_user()
    app = _app()
    with app.test_request_context("/user/dashboard"):
        user_routes._establish_user_session(user)
        assert user_routes._current_user()["id"] == user["id"]
        db_utils.get_conn().execute(
            "UPDATE users SET session_version=session_version+1 WHERE id=?", (user["id"],)
        )
        db_utils.get_conn().commit()
        assert user_routes._current_user() is None
        assert "user_id" not in session


def test_password_changes_and_admin_reset_increment_session_version(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "password.db")
    user = _create_user()
    updated = member_service.change_user_password(
        user["id"], "Old password 123!", "New password 456!"
    )
    assert updated["session_version"] == 2
    assert updated["password_changed_at"]

    reset = member_service.admin_reset_user_password(user["id"], "Admin reset password 789!")
    assert reset["session_version"] == 3


def test_disabling_user_revokes_existing_sessions(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "disabled.db")
    user = _create_user()
    result = set_user_status(user["id"], "disabled")
    assert result["user"]["status"] == "disabled"
    assert result["user"]["session_version"] == 2


def test_self_password_change_refreshes_only_current_session(monkeypatch):
    user = {"id": 7, "username": "alice", "session_version": 1}
    updated = {"id": 7, "username": "alice", "session_version": 2}
    monkeypatch.setattr(user_routes, "_current_user", lambda: user)
    monkeypatch.setattr(user_routes, "change_user_password", lambda *args: updated)
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: ("event", True))
    client = _app().test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 7
        sess["user_session_version"] = 1
        sess["user_csrf_token"] = "csrf"
    response = client.post(
        "/user/change-password",
        data={
            "current_password": "Old password 123!",
            "new_password": "New password 456!",
            "new_password2": "New password 456!",
        },
    )
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess["user_session_version"] == 2
        assert sess["user_id"] == 7

def test_api_key_rotate_requires_authenticated_user_before_mutation(monkeypatch):
    rotated = []

    monkeypatch.setattr(user_routes, "_current_user", lambda: None)
    monkeypatch.setattr(
        user_routes,
        "rotate_api_key",
        lambda user_id: rotated.append(user_id) or "unused",
    )

    response = _app().test_client().post(
        "/user/api-key/rotate",
        data={"password": "irrelevant"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/user/login")
    assert rotated == []


def test_api_key_rotate_requires_current_password_before_mutation(monkeypatch):
    user = {
        "id": 7,
        "username": "alice",
        "password_hash": "hash",
        "status": "active",
        "session_version": 1,
    }
    rotated = []
    events = []

    monkeypatch.setattr(user_routes, "_current_user", lambda: user)
    monkeypatch.setattr(
        user_routes,
        "verify_password",
        lambda password, password_hash: False,
    )
    monkeypatch.setattr(
        user_routes,
        "rotate_api_key",
        lambda user_id: rotated.append(user_id) or "unused",
    )
    monkeypatch.setattr(
        user_routes,
        "record_operation",
        lambda **kwargs: events.append(kwargs) or ("event", True),
    )

    response = _app().test_client().post(
        "/user/api-key/rotate",
        data={"password": "wrong"},
    )

    assert response.status_code == 403
    assert rotated == []
    assert events[-1]["action_code"] == "user.api_key.rotate_failed"
    assert events[-1]["error_code"] == "invalid_password"


def test_api_key_rotate_calls_rotation_only_after_valid_current_password(monkeypatch):
    user = {
        "id": 7,
        "username": "alice",
        "password_hash": "hash",
        "status": "active",
        "session_version": 1,
    }
    rotated = []
    events = []

    monkeypatch.setattr(user_routes, "_current_user", lambda: user)
    monkeypatch.setattr(
        user_routes,
        "verify_password",
        lambda password, password_hash: password == "correct",
    )
    monkeypatch.setattr(
        user_routes,
        "rotate_api_key",
        lambda user_id: rotated.append(user_id) or "TEST_ROTATED_VALUE",
    )
    monkeypatch.setattr(
        user_routes,
        "record_operation",
        lambda **kwargs: events.append(kwargs) or ("event", True),
    )

    response = _app().test_client().post(
        "/user/api-key/rotate",
        data={"password": "correct"},
    )

    assert response.status_code == 200
    assert rotated == [7]
    assert events[-1]["action_code"] == "user.api_key.rotate"
    assert events[-1]["success"] is True

