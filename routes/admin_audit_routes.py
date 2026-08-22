# -*- coding: utf-8 -*-
"""Administrator-only operation and API access history pages."""
from __future__ import annotations

import csv
import hmac
import io
import json
import secrets
from datetime import datetime
from html import escape
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, redirect, request, session

import config
from config import ADMIN_IP_WHITELIST, ADMIN_USERNAME
from services.audit_repository import (
    get_api_access_log,
    get_operation_log,
    query_api_access_logs,
    query_api_access_logs_for_export,
    query_operation_logs,
    query_operation_logs_for_export,
)
from services.audit_security import mask_email, mask_phone, mask_sensitive_structure, safe_csv_cell
from services.audit_service import record_operation
from services.web_security import client_ip
from services.admin_auth import verify_admin_confirmation

admin_audit_bp = Blueprint("admin_audit", __name__)


@admin_audit_bp.before_request
def restrict_admin_ip():
    if not ADMIN_IP_WHITELIST:
        return None
    remote_ip = client_ip()
    allowed = {ip.strip() for ip in ADMIN_IP_WHITELIST if ip.strip()}
    if remote_ip not in allowed:
        return "当前 IP 不允许访问后台", 403
    return None


def _is_admin() -> bool:
    return session.get("admin_logged_in") is True


def _admin_csrf_token() -> str:
    token = str(session.get("admin_csrf_token") or "")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token


def _admin_nav() -> str:
    return """
    <nav class="admin-nav" aria-label="后台导航">
      <a href="/admin/members">套餐操作</a>
      <a href="/admin/members/list">用户列表</a>
      <a href="/admin/password-reset/list">找回密码申请</a>
      <a href="/admin/users/reset-password">重置密码</a>
      <a href="/admin/operation-history">操作历史</a>
      <a href="/admin/data-access-history">数据访问历史</a>
      <a href="/admin/api-docs">API文档管理</a>
        <a href="/admin/interface-tester">市场接口测试台</a>
      <form method="post" action="/admin/logout" class="csp-r5-6b8b63d565c4986a"><button type="submit">退出</button></form>
    </nav>
    """


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="admin-csrf-token" content="{escape(_admin_csrf_token(), quote=True)}">
<title>{escape(title)}</title><link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-admin-audit-routes-l77-a92cad9dfd.css"></head><body>{_admin_nav()}{body}</body></html>"""


def _filters(kind: str) -> dict[str, Any]:
    keys = {
        "operation": ["start_time", "end_time", "action_code", "action_category", "actor_type", "target_user_id", "status_code", "client_ip", "success", "actor", "target", "keyword"],
        "api": ["start_time", "end_time", "provider", "api_name", "request_method", "status_code", "auth_state", "package_code", "required_scope", "client_ip", "success", "user", "path", "min_duration_ms", "max_duration_ms"],
    }[kind]
    return {key: request.args.get(key, "").strip() for key in keys if request.args.get(key, "").strip()}


def _page_args() -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", "50"))
    except ValueError:
        page_size = 50
    return page, page_size


def _query_string_without(*names: str, **updates: Any) -> str:
    values = request.args.to_dict(flat=True)
    for name in names:
        values.pop(name, None)
    for key, value in updates.items():
        values[key] = str(value)
    from urllib.parse import urlencode
    return urlencode(values)


def _filters_html(kind: str) -> str:
    f = request.args
    common = f"""
<label>开始时间<input name="start_time" value="{escape(f.get('start_time',''))}" placeholder="2026-07-01 00:00:00"></label>
<label>结束时间<input name="end_time" value="{escape(f.get('end_time',''))}" placeholder="2026-07-31 23:59:59"></label>
<label>结果<select name="success"><option value="">全部</option><option value="1" {'selected' if f.get('success')=='1' else ''}>成功</option><option value="0" {'selected' if f.get('success')=='0' else ''}>失败</option></select></label>
<label>状态码<input name="status_code" value="{escape(f.get('status_code',''))}" size="8"></label>
<label>IP<input name="client_ip" value="{escape(f.get('client_ip',''))}"></label>"""
    if kind == "operation":
        extra = f"""
<label>操作代码<input name="action_code" value="{escape(f.get('action_code',''))}"></label>
<label>操作分类<input name="action_category" value="{escape(f.get('action_category',''))}"></label>
<label>操作者类型<select name="actor_type"><option value="">全部</option>{''.join(f'<option value="{x}" {"selected" if f.get("actor_type")==x else ""}>{x}</option>' for x in ('admin','user','anonymous','system'))}</select></label>
<label>目标用户ID<input name="target_user_id" value="{escape(f.get('target_user_id',''))}" inputmode="numeric"></label>
<label>操作者<input name="actor" value="{escape(f.get('actor',''))}"></label>
<label>目标用户<input name="target" value="{escape(f.get('target',''))}" placeholder="ID/用户名/手机号/邮箱"></label>
<label>关键词<input name="keyword" value="{escape(f.get('keyword',''))}"></label>"""
    else:
        extra = f"""
<label>用户<input name="user" value="{escape(f.get('user',''))}" placeholder="ID/用户名/手机号/邮箱"></label>
<label>数据源<input name="provider" value="{escape(f.get('provider',''))}"></label>
<label>接口<input name="api_name" value="{escape(f.get('api_name',''))}"></label>
<label>方法<select name="request_method"><option value="">全部</option>{''.join(f'<option value="{x}" {"selected" if f.get("request_method")==x else ""}>{x}</option>' for x in ('GET','POST','PUT','PATCH','DELETE'))}</select></label>
<label>认证状态<input name="auth_state" value="{escape(f.get('auth_state',''))}"></label>
<label>套餐<input name="package_code" value="{escape(f.get('package_code',''))}"></label>
<label>Scope<input name="required_scope" value="{escape(f.get('required_scope',''))}"></label>
<label>路径<input name="path" value="{escape(f.get('path',''))}"></label>
<label>最小耗时(ms)<input name="min_duration_ms" value="{escape(f.get('min_duration_ms',''))}" size="8"></label>
<label>最大耗时(ms)<input name="max_duration_ms" value="{escape(f.get('max_duration_ms',''))}" size="8"></label>"""
    return f"<form class='panel filters' method='get'>{common}{extra}<label>每页<select name='page_size'>{''.join(f'<option value="{n}" {"selected" if f.get("page_size","50")==str(n) else ""}>{n}</option>' for n in (20,50,100,200))}</select></label><button type='submit'>查询</button><a href='{request.path}'>清空筛选</a></form>"


def _stats_html(stats: dict[str, Any], kind: str) -> str:
    if kind == "operation":
        values = [
            ("操作总数", stats.get("total", 0)), ("成功", stats.get("success_count", 0)),
            ("失败", stats.get("failure_count", 0)), ("涉及用户", stats.get("target_user_count", 0)),
            ("管理员操作", stats.get("admin_count", 0)), ("用户操作", stats.get("user_count", 0)),
        ]
    else:
        slow = stats.get("slowest_api") or {}
        values = [
            ("请求总数", stats.get("total", 0)), ("成功", stats.get("success_count", 0)),
            ("失败", stats.get("failure_count", 0)), ("独立用户", stats.get("user_count", 0)),
            ("匿名", stats.get("anonymous_count", 0)), ("平均耗时", f"{stats.get('average_duration_ms',0)} ms"),
            ("401", stats.get("unauthorized_count", 0)), ("402", stats.get("subscription_required_count", 0)),
            ("403", stats.get("forbidden_count", 0)), ("429", stats.get("rate_limited_count", 0)),
            ("5xx", stats.get("server_error_count", 0)),
            ("最慢接口", f"{slow.get('provider','')}/{slow.get('api_name','')} {slow.get('duration_ms','')} ms" if slow else "-")
        ]
    return "<section class='stats'>" + "".join(f"<div class='stat'><b>{escape(str(k))}</b><div>{escape(str(v))}</div></div>" for k, v in values) + "</section>"


def _pagination(result: dict[str, Any]) -> str:
    page, pages = int(result.get("page", 1)), int(result.get("pages", 1))
    prev_link = f"<a href='?{escape(_query_string_without('page', page=max(1,page-1)))}'>上一页</a>" if page > 1 else ""
    next_link = f"<a href='?{escape(_query_string_without('page', page=min(pages,page+1)))}'>下一页</a>" if page < pages else ""
    return f"<div class='pagination'>{prev_link}<span>第 {page}/{pages} 页，共 {result.get('total',0)} 条</span>{next_link}</div>"


def _json_preview(value: Any, limit: int = 180) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def _reveal_script() -> str:
    return """
<script>
async function revealSensitive(tableName, eventId, fields, targets) {
  const password = window.prompt('请输入当前管理员密码进行二次确认：');
  if (!password) return;
  const csrfMeta = document.querySelector('meta[name="admin-csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.content : '';
  try {
    const response = await fetch('/admin/audit/reveal-sensitive', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      credentials: 'same-origin',
      cache: 'no-store',
      body: JSON.stringify({table: tableName, event_id: eventId, fields: fields, password: password})
    });
    const rawText = await response.text();
    let result = {};
    try { result = rawText ? JSON.parse(rawText) : {}; } catch (parseError) {
      result = {message: rawText || ('HTTP ' + response.status)};
    }
    if (!response.ok || !result.success) {
      window.alert(result.message || result.msg || ('查看失败（HTTP ' + response.status + '）'));
      return;
    }
    Object.keys(result.data || {}).forEach(function(field) {
      const element = document.getElementById(targets[field]);
      if (element) { element.textContent = result.data[field] || ''; element.hidden = false; }
    });
  } catch (error) {
    window.alert('查看失败：' + error);
  }
}

document.addEventListener('click', function(event) {
  const button = event.target.closest('.js-reveal-sensitive');
  if (!button) return;
  const tableName = button.dataset.table || '';
  const eventId = button.dataset.eventId || '';
  const fields = tableName === 'operation'
    ? ['target_phone', 'target_email']
    : ['phone_snapshot', 'email_snapshot'];
  const prefix = tableName === 'operation' ? 'op-' : 'api-';
  const targets = tableName === 'operation'
    ? {target_phone: prefix + 'phone-' + eventId, target_email: prefix + 'email-' + eventId}
    : {phone_snapshot: prefix + 'phone-' + eventId, email_snapshot: prefix + 'email-' + eventId};
  revealSensitive(tableName, eventId, fields, targets);
});
</script>
"""


@admin_audit_bp.get("/operation-history")
def operation_history():
    if not _is_admin():
        return redirect("/admin/login")
    filters, (page, size) = _filters("operation"), _page_args()
    result = query_operation_logs(filters, page, size)
    rows = []
    for row in result["items"]:
        rows.append(f"""<tr><td>{escape(str(row.get('created_at','')))}</td>
<td class="{'ok' if row.get('success') else 'fail'}">{'成功' if row.get('success') else '失败'}</td>
<td>{escape(str(row.get('action_name','')))}<br><code>{escape(str(row.get('action_code','')))}</code></td>
<td>{escape(str(row.get('actor_name') or row.get('actor_type') or ''))}</td>
<td>{escape(str(row.get('target_username') or '-'))}（{escape(str(row.get('target_user_id') or '-'))}）</td>
<td><span id="op-phone-{escape(str(row.get('event_id','')))}">{escape(mask_phone(str(row.get('target_phone') or '')))}</span></td><td><span id="op-email-{escape(str(row.get('event_id','')))}">{escape(mask_email(str(row.get('target_email') or '')))}</span><br><button type="button" class="js-reveal-sensitive" data-table="operation" data-event-id="{escape(str(row.get('event_id','')), quote=True)}">查看完整信息</button></td>
<td><code>{escape(_json_preview(mask_sensitive_structure({'before': row.get('before_data'), 'after': row.get('after_data')})))}</code></td>
<td>{escape(str(row.get('client_ip','')))}</td><td><a href="/admin/operation-history/detail/{escape(str(row.get('event_id','')))}">详情</a></td></tr>""")
    body = f"""<h1>操作历史</h1>{_stats_html(result['stats'],'operation')}{_filters_html('operation')}
<div class='panel actions'><a href='/admin/operation-history/export.csv?{escape(request.query_string.decode('utf-8','ignore'))}'>导出脱敏CSV</a>
<form method='post' action='/admin/operation-history/export-full.csv' class='csp-r5-9c40389b4ad89c12'><input type='password' name='password' required placeholder='管理员密码'><input type='hidden' name='filters' value='{escape(json.dumps(filters,ensure_ascii=False))}'><button class='danger' type='submit'>导出完整CSV</button></form></div>
<div class='table-wrap'><table><thead><tr><th>时间</th><th>结果</th><th>操作</th><th>操作者</th><th>目标用户</th><th>手机号</th><th>邮箱</th><th>变化摘要</th><th>IP</th><th>详情</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="10">暂无记录</td></tr>'}</tbody></table></div>{_pagination(result)}{_reveal_script()}"""
    return _page("操作历史", body)


@admin_audit_bp.get("/data-access-history")
def data_access_history():
    if not _is_admin():
        return redirect("/admin/login")
    filters, (page, size) = _filters("api"), _page_args()
    result = query_api_access_logs(filters, page, size)
    rows = []
    for row in result["items"]:
        user = f"{row.get('username_snapshot') or ''}（{row.get('user_id')}）" if row.get("user_id") is not None else "匿名"
        rows.append(f"""<tr><td>{escape(str(row.get('created_at','')))}</td><td>{escape(user)}</td>
<td><span id="api-phone-{escape(str(row.get('event_id','')))}">{escape(mask_phone(str(row.get('phone_snapshot') or '')))}</span><span id="api-email-{escape(str(row.get('event_id','')))}" hidden>{escape(mask_email(str(row.get('email_snapshot') or '')))}</span><br><button type="button" class="js-reveal-sensitive" data-table="api" data-event-id="{escape(str(row.get('event_id','')), quote=True)}">查看完整信息</button></td><td>{escape(str(row.get('provider','')))}</td><td>{escape(str(row.get('api_name','')))}</td>
<td>{escape(str(row.get('request_method','')))}</td><td class="{'ok' if row.get('success') else 'fail'}">{escape(str(row.get('status_code','')))}</td>
<td>{escape(str(row.get('duration_ms','')))} ms</td><td>{escape(str(row.get('auth_state','')))}</td><td>{escape(str(row.get('client_ip','')))}</td>
<td><code>{escape(_json_preview(mask_sensitive_structure(row.get('request_params') or {})))}</code></td><td><a href="/admin/data-access-history/detail/{escape(str(row.get('event_id','')))}">详情</a></td></tr>""")
    body = f"""<h1>数据访问历史</h1>{_stats_html(result['stats'],'api')}{_filters_html('api')}
<div class='panel actions'><a href='/admin/data-access-history/export.csv?{escape(request.query_string.decode('utf-8','ignore'))}'>导出脱敏CSV</a>
<form method='post' action='/admin/data-access-history/export-full.csv' class='csp-r5-9c40389b4ad89c12'><input type='password' name='password' required placeholder='管理员密码'><input type='hidden' name='filters' value='{escape(json.dumps(filters,ensure_ascii=False))}'><button class='danger' type='submit'>导出完整CSV</button></form></div>
<div class='table-wrap'><table><thead><tr><th>时间</th><th>用户</th><th>手机号</th><th>数据源</th><th>接口</th><th>方法</th><th>状态</th><th>耗时</th><th>认证状态</th><th>IP</th><th>参数</th><th>详情</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="12">暂无记录</td></tr>'}</tbody></table></div>{_pagination(result)}{_reveal_script()}"""
    return _page("数据访问历史", body)


def _masked_detail(record: dict[str, Any], kind: str) -> dict[str, Any]:
    del kind
    masked = mask_sensitive_structure(record)
    return dict(masked) if isinstance(masked, dict) else {}


@admin_audit_bp.get("/operation-history/detail/<event_id>")
def operation_detail(event_id: str):
    if not _is_admin():
        return redirect("/admin/login")
    row = get_operation_log(event_id)
    if not row:
        return jsonify({"success": False, "message": "记录不存在"}), 404
    response = jsonify({"success": True, "data": _masked_detail(row, "operation")})
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_audit_bp.get("/data-access-history/detail/<event_id>")
def api_detail(event_id: str):
    if not _is_admin():
        return redirect("/admin/login")
    row = get_api_access_log(event_id)
    if not row:
        return jsonify({"success": False, "message": "记录不存在"}), 404
    response = jsonify({"success": True, "data": _masked_detail(row, "api")})
    response.headers["Cache-Control"] = "no-store"
    return response


def _audit_admin(action_code: str, action_name: str, *, success: bool, status_code: int, target_user: dict[str, Any] | None = None, request_data: Any = None, related_event_id: str = "", error_code: str = "", error_message: str = "", strict: bool = False) -> tuple[str, bool]:
    return record_operation(
        actor_type="admin", actor_id=None, actor_name=ADMIN_USERNAME,
        target_user=target_user, action_category="audit", action_code=action_code,
        action_name=action_name, success=success, status_code=status_code,
        error_code=error_code, error_message=error_message,
        request_data=request_data or {}, related_event_id=related_event_id, strict=strict,
    )


@admin_audit_bp.post("/audit/reveal-sensitive")
def reveal_sensitive():
    if not _is_admin():
        return jsonify({"success": False, "message": "未登录管理员"}), 401
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    table = str(payload.get("table") or "")
    event_id = str(payload.get("event_id") or "")
    raw_fields = payload.get("fields") or []
    if isinstance(raw_fields, str):
        raw_fields = [item.strip() for item in raw_fields.split(",") if item.strip()]
    allowed = {
        "operation": {"target_phone", "target_email"},
        "api": {"phone_snapshot", "email_snapshot"},
    }
    fields = [str(item) for item in raw_fields if str(item) in allowed.get(table, set())]
    getter: Callable[[str], dict[str, Any] | None] | None = get_operation_log if table == "operation" else get_api_access_log if table == "api" else None
    record = getter(event_id) if getter else None
    target_user = None
    if record:
        target_user = {
            "id": record.get("target_user_id") if table == "operation" else record.get("user_id"),
            "username": record.get("target_username") if table == "operation" else record.get("username_snapshot"),
            "phone": record.get("target_phone") if table == "operation" else record.get("phone_snapshot"),
            "email": record.get("target_email") if table == "operation" else record.get("email_snapshot"),
        }
    if not verify_admin_confirmation(str(payload.get("password") or "")):
        _audit_admin("admin.sensitive_reveal", "查看完整敏感信息", success=False, status_code=403, target_user=target_user, request_data={"table": table, "event_id": event_id, "fields": fields}, related_event_id=event_id, error_code="admin_password_invalid", error_message="管理员二次验证失败")
        return jsonify({"success": False, "message": "管理员密码错误"}), 403
    if not record or not fields:
        _audit_admin("admin.sensitive_reveal", "查看完整敏感信息", success=False, status_code=404, target_user=target_user, request_data={"table": table, "event_id": event_id, "fields": fields}, related_event_id=event_id, error_code="audit_record_not_found", error_message="记录或字段不存在")
        return jsonify({"success": False, "message": "记录或字段不存在"}), 404
    _, durable = _audit_admin("admin.sensitive_reveal", "查看完整敏感信息", success=True, status_code=200, target_user=target_user, request_data={"table": table, "event_id": event_id, "fields": fields}, related_event_id=event_id, strict=True)
    if not durable:
        return jsonify({"success": False, "message": "审计系统暂不可用，禁止查看完整敏感信息"}), 503
    response = jsonify({"success": True, "data": {field: record.get(field) or "" for field in fields}})
    response.headers["Cache-Control"] = "no-store"
    return response


def _export_filters(kind: str) -> dict[str, Any]:
    if request.method == "GET":
        return _filters(kind)
    raw = request.form.get("filters") or ""
    if raw:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return {str(k): v for k, v in value.items()}
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {key: value for key, value in request.form.items() if key not in {"password", "filters"} and value}


def _csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows([[safe_csv_cell(cell) for cell in row] for row in rows])
    response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _operation_csv_rows(records: list[dict[str, Any]], full: bool) -> tuple[list[str], list[list[Any]]]:
    headers = ["时间", "结果", "操作代码", "操作名称", "操作者类型", "操作者", "目标用户ID", "目标用户名", "手机号", "邮箱", "状态码", "错误代码", "错误信息", "IP", "请求路径", "操作前", "操作后", "业务参数", "事件ID"]
    rows = []
    for r in records:
        view = r if full else mask_sensitive_structure(r)
        rows.append([view.get("created_at"), "成功" if view.get("success") else "失败", view.get("action_code"), view.get("action_name"), view.get("actor_type"), view.get("actor_name"), view.get("target_user_id"), view.get("target_username"), view.get("target_phone"), view.get("target_email"), view.get("status_code"), view.get("error_code"), view.get("error_message"), view.get("client_ip"), view.get("request_path"), view.get("before_data"), view.get("after_data"), view.get("request_data"), view.get("event_id")])
    return headers, rows


def _api_csv_rows(records: list[dict[str, Any]], full: bool) -> tuple[list[str], list[list[Any]]]:
    headers = ["时间", "结果", "用户ID", "用户名", "手机号", "邮箱", "认证状态", "Token指纹", "数据源", "接口", "方法", "路径", "Scope", "套餐", "状态码", "耗时ms", "错误代码", "错误信息", "IP", "请求参数", "事件ID"]
    rows = []
    for r in records:
        view = r if full else mask_sensitive_structure(r)
        rows.append([view.get("created_at"), "成功" if view.get("success") else "失败", view.get("user_id"), view.get("username_snapshot"), view.get("phone_snapshot"), view.get("email_snapshot"), view.get("auth_state"), view.get("token_fingerprint"), view.get("provider"), view.get("api_name"), view.get("request_method"), view.get("request_path"), view.get("required_scope"), view.get("package_code"), view.get("status_code"), view.get("duration_ms"), view.get("error_code"), view.get("error_message"), view.get("client_ip"), view.get("request_params"), view.get("event_id")])
    return headers, rows


def _export(kind: str, full: bool):
    if not _is_admin():
        return redirect("/admin/login")
    filters = _export_filters(kind)
    max_rows = max(1, int(getattr(config, "AUDIT_CSV_EXPORT_MAX_ROWS", 50000)))
    query = query_operation_logs_for_export if kind == "operation" else query_api_access_logs_for_export
    records = query(filters, max_rows + 1)
    if len(records) > max_rows:
        return jsonify({"success": False, "message": f"导出结果超过 {max_rows} 条，请缩小筛选范围"}), 413
    action_name = ("完整" if full else "脱敏") + ("操作历史" if kind == "operation" else "访问历史") + "CSV导出"
    if full:
        password = request.form.get("password", "")
        if not verify_admin_confirmation(str(password)):
            _audit_admin("admin.audit_export_full", action_name, success=False, status_code=403, request_data={"history_type": kind, "filters": filters, "row_count": len(records)}, error_code="admin_password_invalid", error_message="管理员二次验证失败")
            return jsonify({"success": False, "message": "管理员密码错误"}), 403
        _, durable = _audit_admin("admin.audit_export_full", action_name, success=True, status_code=200, request_data={"history_type": kind, "filters": filters, "row_count": len(records)}, strict=True)
        if not durable:
            return jsonify({"success": False, "message": "审计系统暂不可用，禁止导出完整敏感信息"}), 503
    else:
        _audit_admin("admin.audit_export_masked", action_name, success=True, status_code=200, request_data={"history_type": kind, "filters": filters, "row_count": len(records)})
    headers, rows = _operation_csv_rows(records, full) if kind == "operation" else _api_csv_rows(records, full)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _csv_response(f"{kind}_audit_{'full' if full else 'masked'}_{stamp}.csv", headers, rows)


@admin_audit_bp.get("/operation-history/export.csv")
def export_operation_masked():
    return _export("operation", False)


@admin_audit_bp.post("/operation-history/export-full.csv")
def export_operation_full():
    return _export("operation", True)


@admin_audit_bp.get("/data-access-history/export.csv")
def export_api_masked():
    return _export("api", False)


@admin_audit_bp.post("/data-access-history/export-full.csv")
def export_api_full():
    return _export("api", True)
