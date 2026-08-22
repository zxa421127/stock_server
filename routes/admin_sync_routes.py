# -*- coding: utf-8 -*-
"""Administrative maintenance endpoints authenticated by an admin API token."""
from flask import Blueprint, g, jsonify

import config
from middleware.auth import require_scope
from services.audit_service import record_operation

admin_sync_bp = Blueprint("admin_sync", __name__)


def _actor() -> dict:
    return dict(getattr(g, "current_user", {}) or {})


def _record(action_code: str, action_name: str, success: bool, status_code: int, error: Exception | str | None = None):
    actor = _actor()
    return record_operation(
        actor_type="admin",
        actor_id=actor.get("id"),
        actor_name=str(actor.get("username") or "admin-api"),
        target_user=None,
        action_category="system_maintenance",
        action_code=action_code,
        action_name=action_name,
        success=success,
        status_code=status_code,
        error_code="sync_failed" if error else "",
        error_message=str(error or ""),
        request_data={"trigger": "manual_api"},
    )


def _disabled_response():
    return jsonify({
        "success": False,
        "code": 503,
        "data": [],
        "msg": "飞书同步未启用，请先在 .env 设置 ENABLE_FEISHU_SYNC=True 并补全飞书配置",
    }), 503


@admin_sync_bp.route("/sync/feishu", methods=["POST"])
@require_scope("admin:sync")
def trigger_feishu_sync():
    if not config.ENABLE_FEISHU_SYNC:
        _record("admin.feishu_sync", "触发本地到飞书同步", False, 503, "飞书同步未启用")
        return _disabled_response()
    try:
        from services.feishu_sync_service import trigger_sync_now
        trigger_sync_now()
        _record("admin.feishu_sync", "触发本地到飞书同步", True, 200)
        return jsonify({"success": True, "code": 200, "data": [], "msg": "已触发本地→飞书同步"})
    except Exception as exc:
        _record("admin.feishu_sync", "触发本地到飞书同步", False, 500, exc)
        raise


@admin_sync_bp.route("/sync/bidding", methods=["POST"])
@require_scope("admin:sync")
def trigger_bidding_sync():
    if not config.ENABLE_FEISHU_SYNC:
        _record("admin.bidding_sync", "触发竞价同步", False, 503, "飞书同步未启用")
        return _disabled_response()
    try:
        from services.feishu_sync_service import trigger_bidding_sync_now
        trigger_bidding_sync_now()
        _record("admin.bidding_sync", "触发竞价同步", True, 200)
        return jsonify({"success": True, "code": 200, "data": [], "msg": "已触发竞价同步"})
    except Exception as exc:
        _record("admin.bidding_sync", "触发竞价同步", False, 500, exc)
        raise
