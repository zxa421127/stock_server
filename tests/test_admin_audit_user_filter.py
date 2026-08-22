from __future__ import annotations

from flask import Flask

from routes import admin_audit_routes
from services import audit_repository


def test_operation_where_supports_exact_target_user_and_category():
    where, params = audit_repository._operation_where({
        "target_user_id": 7,
        "action_category": "authentication",
        "actor_type": "anonymous",
    })
    assert "target_user_id=?" in where
    assert "action_category=?" in where
    assert "actor_type=?" in where
    assert params == ["authentication", "anonymous", 7]


def test_operation_route_collects_target_user_and_category_filters():
    app = Flask(__name__)
    with app.test_request_context("/admin/operation-history?target_user_id=7&action_category=authentication"):
        filters = admin_audit_routes._filters("operation")
    assert filters["target_user_id"] == "7"
    assert filters["action_category"] == "authentication"


def test_operation_filter_ui_includes_anonymous_and_exact_target_user():
    app = Flask(__name__)
    with app.test_request_context("/admin/operation-history?target_user_id=7&actor_type=anonymous"):
        html = admin_audit_routes._filters_html("operation")
    assert '<option value="anonymous" selected>anonymous</option>' in html
    assert 'name="target_user_id"' in html
    assert 'value="7"' in html
