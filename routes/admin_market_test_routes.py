# -*- coding: utf-8 -*-
"""Administrator-only market interface testing center."""
from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session

import config
from services.admin_api_test_batch_service import get_admin_api_test_batch_service
from services.admin_api_test_cleanup_service import get_admin_api_test_cleanup_service
from services.admin_api_test_repository import AdminApiTestRepository
from services.admin_api_test_storage import AdminApiTestStorage
from services.admin_api_test_security import redact_sensitive
from services.audit_service import record_operation
from services.market_interface_spec_service import MarketInterfaceSpecService
from services.tushare_spec_sync_service import TushareSpecSyncService
from services.tushare_spec_monitor_service import get_tushare_spec_monitor_service
from services.admin_auth import verify_admin_confirmation


admin_market_test_bp = Blueprint("admin_market_test", __name__)

_spec_service_override = None
_batch_service_override = None
_cleanup_service_override = None
_storage_override = None
_repository_override = None
_monitor_service_override = None


def _specs() -> MarketInterfaceSpecService:
    return _spec_service_override or MarketInterfaceSpecService()


def _batch():
    return _batch_service_override or get_admin_api_test_batch_service()


def _cleanup():
    return _cleanup_service_override or get_admin_api_test_cleanup_service()


def _storage() -> AdminApiTestStorage:
    return _storage_override or AdminApiTestStorage()


def _repo() -> AdminApiTestRepository:
    return _repository_override or AdminApiTestRepository()


def _monitor():
    return _monitor_service_override or get_tushare_spec_monitor_service()


def _payload() -> dict[str, Any]:
    value = request.get_json(silent=True)
    if isinstance(value, dict):
        return value
    return request.form.to_dict(flat=True)


def _success(data: Any = None, message: str = "操作成功", status: int = 200):
    return jsonify({"success": True, "code": status, "data": data, "message": message}), status


def _error(
    message: str, status: int = 400, *, code: str = "", data: Any = None,
):
    return jsonify({
        "success": False, "code": status, "data": data,
        "message": message, "error_code": code,
    }), status


def _admin_name() -> str:
    return str(config.ADMIN_USERNAME or "admin")


def _audit(action_code: str, action_name: str, success: bool, status_code: int, *, request_data=None, after_data=None, error="") -> None:
    try:
        record_operation(
            actor_type="admin", actor_id=None, actor_name=_admin_name(), target_user=None,
            action_category="market_interface_test", action_code=action_code,
            action_name=action_name, success=success, status_code=status_code,
            error_code="admin_interface_test_failed" if error else "", error_message=str(error or ""),
            request_data=redact_sensitive(request_data or {}),
            after_data=redact_sensitive(after_data or {}),
        )
    except Exception:
        logging.exception("管理员接口测试操作审计写入失败: %s", action_code)


@admin_market_test_bp.before_request
def _require_admin():
    if session.get("admin_logged_in") is not True:
        return redirect("/admin/login")
    return None


@admin_market_test_bp.get("/interface-tester")
def interface_tester_page():
    csrf = str(session.get("admin_csrf_token") or "")
    specs = _specs()
    specs.ensure_seed_release()
    default_retention_days = _repo().get_default_retention_days(
        config.ADMIN_API_TEST_RETENTION_DAYS
    )
    return render_template(
        "admin/interface_tester.html",
        csrf_token=csrf,
        default_retention_days=default_retention_days,
        current_spec_version=specs.current_version(),
        coverage=specs.coverage_statistics(),
        disk=_cleanup().disk_status(),
        candidate_count=len(specs.candidate_summary()),
        spec_monitor=_monitor().dashboard(),
    )


@admin_market_test_bp.get("/interface-tester/settings.json")
def interface_tester_settings():
    days = _repo().get_default_retention_days(config.ADMIN_API_TEST_RETENTION_DAYS)
    row = _repo().get_setting("default_retention_days") or {}
    return _success({
        "default_retention_days": days,
        "updated_at": row.get("updated_at", ""),
        "updated_by": row.get("updated_by", ""),
    })[0]


@admin_market_test_bp.post("/interface-tester/settings/retention")
def update_interface_tester_retention():
    payload = _payload()
    try:
        saved = _repo().set_default_retention_days(
            payload.get("days"), updated_by=_admin_name()
        )
    except ValueError as exc:
        return _error(str(exc), 400)
    data = {
        "default_retention_days": saved["days"],
        "updated_at": saved.get("updated_at", ""),
        "updated_by": saved.get("updated_by", ""),
    }
    _audit(
        "admin.interface_test.default_retention",
        "修改接口测试默认保留天数", True, 200,
        request_data={"days": saved["days"]}, after_data=data,
    )
    return _success(data, "默认保留天数已保存")[0]


@admin_market_test_bp.get("/interface-tester/catalog.json")
def interface_catalog():
    specs = _specs()
    provider = str(request.args.get("provider") or "").strip().lower()
    category = str(request.args.get("category") or "").strip()
    keyword = str(request.args.get("q") or "").strip()

    all_rows = specs.list_effective_specs()
    provider_counts: dict[str, int] = {}
    for row in all_rows:
        name = str(row.get("provider") or "其他").strip().lower() or "其他"
        provider_counts[name] = provider_counts.get(name, 0) + 1
    providers = [
        {"name": name, "count": count}
        for name, count in sorted(provider_counts.items(), key=lambda item: item[0])
    ]

    category_base = specs.list_effective_specs(provider=provider) if provider else all_rows
    category_counts: dict[str, dict[str, Any]] = {}
    for row in category_base:
        name = str(row.get("category") or "其他/未分类").strip() or "其他/未分类"
        sort_order = int(row.get("category_sort_order") or 9999)
        current = category_counts.setdefault(name, {"name": name, "count": 0, "sort_order": sort_order})
        current["count"] += 1
        current["sort_order"] = min(int(current["sort_order"]), sort_order)
    categories = sorted(category_counts.values(), key=lambda row: (int(row["sort_order"]), str(row["name"])))

    rows = specs.list_effective_specs(provider=provider, category=category, keyword=keyword)
    compact = [{
        "provider": row.get("provider"), "api_name": row.get("api_name"), "title": row.get("title"),
        "category": row.get("category") or "其他/未分类",
        "category_sort_order": int(row.get("category_sort_order") or 9999),
        "sort_order": int(row.get("sort_order") or 0),
        "scope": row.get("scope"),
        "spec_status": row.get("spec_status"), "change_status": row.get("change_status"),
        "blocking_change": bool(row.get("blocking_change")), "publish_eligible": bool(row.get("publish_eligible")),
        "input_count": len(row.get("input_params") or []), "output_count": len(row.get("output_fields") or []),
        "source_kind": row.get("source_kind"), "official_verified": bool(row.get("official_verified")),
    } for row in rows]
    return jsonify({
        "success": True, "code": 200, "count": len(compact),
        "data": {
            "providers": providers, "categories": categories, "items": compact,
            "coverage": specs.coverage_statistics(), "version": specs.current_version(),
        },
    })


@admin_market_test_bp.get("/interface-tester/spec/<provider>/<api_name>.json")
def interface_spec(provider: str, api_name: str):
    spec = _specs().get_effective_spec(provider, api_name)
    if not spec:
        return _error("接口规格不存在", 404)
    return _success(spec)[0]


@admin_market_test_bp.post("/interface-tester/spec/<provider>/<api_name>/preset")
def save_interface_preset(provider: str, api_name: str):
    payload = _payload()
    params = payload.get("params")
    if not isinstance(params, dict):
        return _error("params必须为JSON对象", 400)
    try:
        release = _specs().save_interface_preset(
            provider, api_name, params,
            name=str(payload.get("name") or "管理员默认参数"),
            updated_by=_admin_name(),
        )
        spec = _specs().get_effective_spec(provider, api_name)
        _audit(
            "admin.interface_spec.preset_update", "修改接口批量测试默认参数", True, 200,
            request_data={"provider": provider, "api_name": api_name, "params": params},
            after_data={"version": release.get("version")},
        )
        return _success({"release": release, "spec": spec}, "批量测试默认参数已保存")[0]
    except KeyError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        _audit(
            "admin.interface_spec.preset_update", "修改接口批量测试默认参数", False, 400,
            request_data={"provider": provider, "api_name": api_name, "params": params},
            error=exc,
        )
        return _error(str(exc), 400)


@admin_market_test_bp.post(
    "/interface-tester/spec-candidates/<candidate_version>/<provider>/<api_name>/preset"
)
def save_candidate_interface_preset(
    candidate_version: str, provider: str, api_name: str,
):
    payload = _payload()
    params = payload.get("params")
    if not isinstance(params, dict):
        return _error("params必须为JSON对象", 400)
    try:
        spec = _specs().update_candidate_preset(
            candidate_version, provider, api_name, params,
            name=str(payload.get("name") or "管理员默认参数"),
            updated_by=_admin_name(),
        )
        _audit(
            "admin.interface_spec.candidate_preset_update",
            "修改候选规格批量测试默认参数", True, 200,
            request_data={
                "candidate_version": candidate_version,
                "provider": provider, "api_name": api_name, "params": params,
            },
            after_data={"publish_eligible": spec.get("publish_eligible")},
        )
        return _success(spec, "候选规格默认参数已保存")[0]
    except KeyError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        _audit(
            "admin.interface_spec.candidate_preset_update",
            "修改候选规格批量测试默认参数", False, 400,
            request_data={
                "candidate_version": candidate_version,
                "provider": provider, "api_name": api_name, "params": params,
            },
            error=exc,
        )
        return _error(str(exc), 400)


@admin_market_test_bp.post(
    "/interface-tester/spec-candidates/<candidate_version>/<provider>/<api_name>/overrides"
)
def save_candidate_interface_overrides(
    candidate_version: str, provider: str, api_name: str,
):
    payload = _payload()
    try:
        spec = _specs().update_candidate_overrides(
            candidate_version, provider, api_name,
            input_overrides=payload.get("input_overrides") or {},
            output_overrides=payload.get("output_overrides") or {},
            validation_rules=payload.get("validation_rules") or [],
            updated_by=_admin_name(),
        )
        _audit(
            "admin.interface_spec.candidate_override_update",
            "修改候选规格规范化和组合校验规则", True, 200,
            request_data={
                "candidate_version": candidate_version, "provider": provider,
                "api_name": api_name,
                "input_overrides": payload.get("input_overrides") or {},
                "output_overrides": payload.get("output_overrides") or {},
                "validation_rules": payload.get("validation_rules") or [],
            },
            after_data={"publish_eligible": spec.get("publish_eligible")},
        )
        return _success(spec, "候选规格规范化规则已保存")[0]
    except KeyError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        _audit(
            "admin.interface_spec.candidate_override_update",
            "修改候选规格规范化和组合校验规则", False, 400,
            request_data=payload, error=exc,
        )
        return _error(str(exc), 400)


@admin_market_test_bp.post("/interface-tester/run")
def run_single_interface():
    payload = _payload()
    if "fields" in payload:
        return _error("输出字段由官方接口规格固定全量返回，不支持用户选择", 400)
    try:
        _cleanup().assert_can_start_batch()
        batch = _batch().create_single_test(
            str(payload.get("provider") or ""), str(payload.get("api_name") or ""),
            params=dict(payload.get("params") or {}),
            mode=str(payload.get("mode") or "upstream"), requested_by=_admin_name(), enqueue=False,
        )
        finished = _batch().run_batch_now(batch["id"])
        item = _repo().list_items(batch["id"])[0]
        _audit("admin.interface_test.single", "管理员单接口测试", True, 200,
               request_data={"provider": item["provider"], "api_name": item["api_name"], "mode": item["mode"]},
               after_data={"batch_id": batch["id"], "status": item["status"], "row_count": item["row_count"]})
        return _success({"batch": finished, "item": item}, "单接口测试完成")[0]
    except (KeyError, ValueError) as exc:
        _audit("admin.interface_test.single", "管理员单接口测试", False, 400, request_data=payload, error=exc)
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 409)
    except Exception as exc:
        logging.exception("管理员单接口测试路由异常")
        _audit("admin.interface_test.single", "管理员单接口测试", False, 500, request_data=payload, error=exc)
        return _error(str(exc), 500)


@admin_market_test_bp.route("/interface-tester/batches", methods=["GET", "POST"])
def batches():
    if request.method == "GET":
        rows = _repo().list_batches(limit=int(request.args.get("limit") or 100), status=str(request.args.get("status") or ""))
        return _success({"items": rows, "disk": _cleanup().disk_status()})[0]
    payload = _payload()
    try:
        _cleanup().assert_can_start_batch()
        interfaces = payload.get("interfaces")
        if isinstance(interfaces, list) and any(isinstance(row, dict) and "fields" in row for row in interfaces):
            return _error("输出字段由官方接口规格固定全量返回，不支持用户选择", 400)
        batch = _batch().create_batch(
            interfaces=interfaces if isinstance(interfaces, list) and interfaces else None,
            requested_by=_admin_name(), mode=str(payload.get("mode") or "upstream"),
            kind="batch",
            retention_days=(
                int(payload["retention_days"])
                if payload.get("retention_days") not in (None, "") else None
            ),
            enqueue=bool(payload.get("start", True)),
        )
        _audit("admin.interface_test.batch_start", "启动管理员批量接口测试", True, 202,
               request_data={"mode": payload.get("mode"), "interface_count": len(interfaces or []) or "all"},
               after_data={"batch_id": batch["id"], "total_count": batch["total_count"]})
        return _success(batch, "批量任务已创建", 202)
    except (KeyError, ValueError) as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 409)


@admin_market_test_bp.get("/interface-tester/batches/<batch_id>.json")
def batch_detail(batch_id: str):
    try:
        progress = _batch().progress(batch_id)
    except KeyError as exc:
        return _error(str(exc), 404)
    return _success({"batch": progress, "items": _repo().list_items(batch_id), "events": _repo().list_events(batch_id)})[0]


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/cancel")
def cancel_batch(batch_id: str):
    try:
        batch = _batch().request_cancel(batch_id)
        _audit("admin.interface_test.batch_cancel", "取消管理员批量接口测试", True, 200, after_data={"batch_id": batch_id})
        return _success(batch, "已请求安全取消")[0]
    except KeyError as exc:
        return _error(str(exc), 404)


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/retry-failed")
def retry_failed(batch_id: str):
    try:
        batch = _batch().retry_failed(batch_id, requested_by=_admin_name(), enqueue=bool(_payload().get("start", True)))
        _audit("admin.interface_test.batch_retry", "重测失败接口", True, 202, after_data={"batch_id": batch["id"], "parent_batch_id": batch_id})
        return _success(batch, "失败接口重测任务已创建", 202)
    except KeyError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        return _error(str(exc), 400)


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/lock")
def lock_batch(batch_id: str):
    reason = str(_payload().get("reason") or "").strip()
    if not reason:
        return _error("锁定原因不能为空", 400)
    batch = _repo().lock_batch(batch_id, locked_by=_admin_name(), reason=reason)
    if not batch:
        return _error("批次不存在", 404)
    _audit("admin.interface_test.batch_lock", "锁定接口测试批次永久保留", True, 200, after_data={"batch_id": batch_id, "reason": reason})
    return _success(batch, "批次已锁定为永久保留")[0]


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/unlock")
def unlock_batch(batch_id: str):
    batch = _repo().unlock_batch(batch_id)
    if not batch:
        return _error("批次不存在", 404)
    _audit("admin.interface_test.batch_unlock", "解除接口测试批次永久保留", True, 200, after_data={"batch_id": batch_id})
    return _success(batch, "批次已解除永久保留")[0]


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/retention")
def change_retention(batch_id: str):
    try:
        days = int(_payload().get("days") or 0)
    except (TypeError, ValueError):
        return _error("保留天数必须为整数", 400)
    try:
        batch = _repo().set_retention_days(batch_id, days)
    except ValueError as exc:
        return _error(str(exc), 400)
    if not batch:
        return _error("批次不存在", 404)
    _audit("admin.interface_test.batch_retention", "修改接口测试批次保留天数", True, 200, after_data={"batch_id": batch_id, "days": days})
    return _success(batch)[0]


@admin_market_test_bp.post("/interface-tester/batches/<batch_id>/delete")
def delete_batch(batch_id: str):
    payload = _payload()
    if not verify_admin_confirmation(str(payload.get("password") or "")):
        return _error("管理员密码校验失败", 403)
    try:
        _cleanup().delete_batch(batch_id)
        _audit("admin.interface_test.batch_delete", "永久删除接口测试批次", True, 200, after_data={"batch_id": batch_id})
        return _success({"batch_id": batch_id}, "批次及完整结果已永久删除")[0]
    except KeyError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        return _error(str(exc), 409)


@admin_market_test_bp.get("/interface-tester/items/<int:item_id>/rows.json")
def result_rows(item_id: int):
    item = _repo().get_item(item_id)
    if not item:
        return _error("测试项目不存在", 404)
    path = str(item.get("result_file_path") or "")
    if not path:
        return _error(
            "本次执行未生成完整结果文件，请查看执行错误", 409,
            code="artifact_not_generated", data={
                "status": item.get("status"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
            },
        )
    try:
        page = int(request.args.get("page") or 1)
        page_size = min(int(request.args.get("page_size") or config.ADMIN_API_TEST_PREVIEW_PAGE_SIZE), config.ADMIN_API_TEST_MAX_PREVIEW_PAGE_SIZE)
        return _success(_storage().read_rows(path, page=page, page_size=page_size))[0]
    except FileNotFoundError:
        return _error("结果文件不存在", 404)
    except Exception as exc:
        return _error(str(exc), 400)


@admin_market_test_bp.get("/interface-tester/items/<int:item_id>/raw.json")
def result_raw(item_id: int):
    item = _repo().get_item(item_id)
    if not item:
        return _error("测试项目不存在", 404)
    if not item.get("result_file_path"):
        return _error(
            "本次执行未生成完整结果文件，请查看执行错误", 409,
            code="artifact_not_generated", data={
                "status": item.get("status"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
            },
        )
    try:
        return _success(_storage().read_response(item["result_file_path"]))[0]
    except FileNotFoundError:
        return _error("结果文件记录存在，但服务器文件已不存在", 410, code="artifact_gone")


@admin_market_test_bp.get("/interface-tester/items/<int:item_id>/download/<kind>")
def download_item_file(item_id: int, kind: str):
    item = _repo().get_item(item_id)
    if not item:
        return _error("测试项目不存在", 404)
    field = {"json": "result_file_path", "csv": "csv_file_path", "request": "request_file_path", "schema": "schema_file_path"}.get(kind)
    if not field:
        return _error("下载类型不支持", 400)
    path = str(item.get(field) or "")
    if not path:
        return _error(
            "本次执行未生成对应文件，请查看执行错误", 409,
            code="artifact_not_generated", data={
                "kind": kind,
                "status": item.get("status"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
            },
        )
    try:
        safe = _storage().safe_resolve(path)
    except ValueError as exc:
        return _error(str(exc), 403)
    if not safe.is_file():
        return _error(
            "文件路径已记录，但服务器上的对应文件已不存在", 410,
            code="artifact_gone", data={"kind": kind, "path_recorded": True},
        )
    return send_file(safe, as_attachment=True, download_name=safe.name)


@admin_market_test_bp.get("/interface-tester/batches/<batch_id>/download.zip")
def download_batch_zip(batch_id: str):
    if not _repo().get_batch(batch_id):
        return _error("批次不存在", 404)
    try:
        path = _storage().safe_resolve(_storage().build_batch_zip(batch_id))
        return send_file(path, as_attachment=True, download_name=path.name)
    except FileNotFoundError as exc:
        return _error(str(exc), 404)


@admin_market_test_bp.get("/interface-tester/spec-candidates.json")
def spec_candidates():
    return _success({"items": _specs().candidate_summary(), "coverage": _specs().coverage_statistics()})[0]


@admin_market_test_bp.get("/interface-tester/spec-candidates/<candidate_version>.json")
def spec_candidate_detail(candidate_version: str):
    try:
        return _success(_specs().load_candidate(candidate_version))[0]
    except (ValueError, FileNotFoundError) as exc:
        return _error(str(exc), 404)


@admin_market_test_bp.get("/interface-tester/spec-monitor.json")
def spec_monitor_status():
    return _success(_monitor().dashboard())[0]


@admin_market_test_bp.post("/interface-tester/spec-monitor/scan")
def scan_official_specs():
    payload = _payload()
    api_names = payload.get("api_names")
    try:
        result = _monitor().scan(
            api_names if isinstance(api_names, list) else None, trigger="manual",
        )
        _audit("admin.interface_spec.monitor_scan", "检查Tushare官网接口规格变化", True, 200, after_data=result)
        return _success(result, "官网检查完成；正式规格未自动覆盖")[0]
    except RuntimeError as exc:
        return _error(str(exc), 409)
    except Exception as exc:
        logging.exception("Tushare官网规格检查失败")
        _audit("admin.interface_spec.monitor_scan", "检查Tushare官网接口规格变化", False, 500, error=exc)
        return _error(str(exc), 502)


@admin_market_test_bp.post("/interface-tester/spec-monitor/alerts/view")
def view_spec_alerts():
    alert_ids = [int(value) for value in (_payload().get("alert_ids") or [])]
    _monitor().repository.mark_alerts_viewed(alert_ids)
    return _success({"updated_count": len(alert_ids)}, "已标记为已查看")[0]


@admin_market_test_bp.post("/interface-tester/spec-monitor/sync")
def sync_spec_alerts():
    payload = _payload()
    alert_ids = [int(value) for value in (payload.get("alert_ids") or [])]
    try:
        result = _monitor().create_candidate_for_alerts(alert_ids)
        _audit(
            "admin.interface_spec.alert_sync", "同步所选Tushare官网规格变化", True, 200,
            request_data={"alert_ids": alert_ids}, after_data=result,
        )
        return _success(result, "已重新读取官网并生成候选；正式规格未自动覆盖")[0]
    except (ValueError, KeyError) as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        logging.exception("同步官网变化提醒失败")
        _audit("admin.interface_spec.alert_sync", "同步所选Tushare官网规格变化", False, 500, request_data={"alert_ids": alert_ids}, error=exc)
        return _error(str(exc), 502)


# Backward-compatible endpoint: it now performs change detection only.
@admin_market_test_bp.post("/interface-tester/spec-sync")
def sync_specs():
    return scan_official_specs()


@admin_market_test_bp.post("/interface-tester/spec-candidates/publish")
def publish_specs():
    payload = _payload()
    if not verify_admin_confirmation(str(payload.get("password") or "")):
        return _error("管理员密码校验失败", 403)
    selected_raw = payload.get("selected") or []
    selected: list[tuple[str, str]] = []
    for row in selected_raw:
        if isinstance(row, dict):
            selected.append((str(row.get("provider") or ""), str(row.get("api_name") or "")))
        elif isinstance(row, (list, tuple)) and len(row) == 2:
            selected.append((str(row[0]), str(row[1])))
    try:
        candidate_version = str(payload.get("candidate_version") or "")
        release = _specs().publish_candidate_selection(
            candidate_version, selected,
            published_by=_admin_name(), note=str(payload.get("note") or ""),
        )
        selected_api_names = [api_name for provider, api_name in selected if provider == "tushare"]
        bound_alert_ids = _monitor().bind_published_release(
            candidate_version=candidate_version, api_names=selected_api_names,
            release_version=release["version"],
        ) if selected_api_names else []
        official_verification = _monitor().verify_published_interfaces(
            selected_api_names, candidate_version=candidate_version,
        ) if bound_alert_ids else {
            "verified": [], "failures": [], "complete": True,
            "skipped": True,
            "reason": "该候选不是由官网变化提醒生成，无需执行提醒闭环复核",
        }
        validation = None
        if bool(payload.get("immediate_validation", True)):
            _cleanup().assert_can_start_batch()
            validation = _batch().create_validation_batch(
                selected, release_id=release["version"], requested_by=_admin_name(), enqueue=True,
            )
        _audit("admin.interface_spec.publish", "发布所选接口规格", True, 200,
               request_data={"candidate_version": payload.get("candidate_version"), "selected_count": len(selected)},
               after_data={"release": release, "validation_batch_id": validation.get("id") if validation else ""})
        return _success({
            "release": release, "validation_batch": validation,
            "official_verification": official_verification,
        }, f"已原子发布所选{len(selected)}个接口规格")[0]
    except (ValueError, KeyError) as exc:
        _audit("admin.interface_spec.publish", "发布所选接口规格", False, 400, request_data=payload, error=exc)
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 409)


@admin_market_test_bp.get("/interface-tester/storage.json")
def storage_status():
    return _success(_cleanup().disk_status())[0]
