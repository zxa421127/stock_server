# -*- coding: utf-8 -*-
"""Independent administrator user detail and edit center."""
from __future__ import annotations

import hmac
import secrets
from html import escape
from urllib.parse import urlencode

from flask import Blueprint, redirect, request, session

from config import ADMIN_USERNAME
from routes.admin_member_routes import _admin_nav, _page, require_admin_session, restrict_admin_ip
from services.admin_user_service import (
    REGISTER_SOURCE_OPTIONS,
    UserNotFoundError,
    UserProfileConflictError,
    UserProfileError,
    UserProfileValidationError,
    get_admin_user_detail,
    set_user_status,
    sync_user_profile_to_feishu,
    update_user_profile,
)
from services.audit_repository import query_operation_logs
from services.audit_service import record_operation

admin_user_bp = Blueprint("admin_user", __name__)


@admin_user_bp.before_request
def _admin_user_access_guard():
    return restrict_admin_ip()


def _csrf_token() -> str:
    token = str(session.get("admin_csrf_token") or "")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token


def _valid_csrf() -> bool:
    expected = str(session.get("admin_csrf_token") or "")
    supplied = str(request.form.get("csrf_token") or "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _audit(
    *,
    target_user: dict | None,
    action_code: str,
    action_name: str,
    success: bool,
    status_code: int,
    error_code: str = "",
    error_message: str = "",
    before_data: dict | None = None,
    after_data: dict | None = None,
    request_data: dict | None = None,
):
    return record_operation(
        actor_type="admin",
        actor_id=None,
        actor_name=ADMIN_USERNAME,
        target_user=target_user,
        action_category="user_management",
        action_code=action_code,
        action_name=action_name,
        success=success,
        status_code=status_code,
        error_code=error_code,
        error_message=error_message,
        before_data=before_data or {},
        after_data=after_data or {},
        request_data=request_data or {},
    )


def _notice_redirect(user_id: int, message: str, kind: str = "ok"):
    query = urlencode({"message": message, "message_type": kind})
    return redirect(f"/admin/users/{int(user_id)}?{query}")


def _source_options(current: str) -> str:
    values = dict(REGISTER_SOURCE_OPTIONS)
    if current and current not in values:
        values[current] = f"保留原值：{current}"
    return "".join(
        f'<option value="{escape(code)}" {"selected" if code == current else ""}>{escape(label)}（{escape(code)}）</option>'
        for code, label in values.items()
    )


def _history_rows(items: list[dict], empty_text: str) -> str:
    if not items:
        return f'<tr><td colspan="7" class="muted">{escape(empty_text)}</td></tr>'
    rows: list[str] = []
    for item in items[:20]:
        result_class = "ok" if item.get("success") else "error"
        result_text = "成功" if item.get("success") else "失败"
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('created_at') or ''))}</td>"
            f"<td class=\"{result_class}\">{result_text}</td>"
            f"<td>{escape(str(item.get('action_name') or ''))}<br><code>{escape(str(item.get('action_code') or ''))}</code></td>"
            f"<td>{escape(str(item.get('client_ip') or ''))}</td>"
            f"<td class=\"ua-cell\">{escape(str(item.get('user_agent') or ''))}</td>"
            f"<td>{escape(str(item.get('error_code') or ''))}</td>"
            f"<td>{escape(str(item.get('error_message') or ''))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _load_histories(user_id: int) -> tuple[list[dict], list[dict]]:
    authentication = query_operation_logs(
        {"target_user_id": int(user_id), "action_category": "authentication"},
        1,
        20,
    )["items"]
    admin_operations = query_operation_logs(
        {"target_user_id": int(user_id), "actor_type": "admin"},
        1,
        20,
    )["items"]
    return authentication, admin_operations


def _render_detail(
    user_id: int,
    *,
    error_message: str = "",
    status_code: int = 200,
    form_values: dict | None = None,
):
    detail = get_admin_user_detail(int(user_id))
    if not detail:
        return _page(
            "用户不存在",
            f"{_admin_nav()}<h2 class='error'>用户不存在</h2><p><a href='/admin/members/list'>返回用户列表</a></p>",
        ), 404

    user = dict(detail["user"])
    if form_values:
        for key in ("phone", "email", "taobao_nick", "register_source"):
            if key in form_values:
                user[key] = form_values[key]
    auth_history, admin_history = _load_histories(int(user_id))
    csrf = _csrf_token()
    current_sub = detail.get("current_subscription") or {}
    scheduled = detail.get("scheduled_subscriptions") or []
    tokens = detail.get("token_summary") or {}
    status = str(user.get("status") or "active")
    next_status = "disabled" if status == "active" else "active"
    next_label = "禁用账号" if next_status == "disabled" else "重新启用"
    status_label = "正常" if status == "active" else "已禁用"
    status_class = "ok" if status == "active" else "error"
    scheduled_html = "<span class='muted'>无</span>" if not scheduled else "<br>".join(
        f"{escape(str(row.get('plan_code') or ''))}：{escape(str(row.get('start_time') or ''))} 至 {escape(str(row.get('expire_time') or ''))}"
        for row in scheduled
    )
    notice = str(request.args.get("message") or "")
    notice_type = str(request.args.get("message_type") or "ok")
    notice_html = ""
    if notice:
        cls = notice_type if notice_type in {"ok", "warning", "error"} else "error"
        notice_html = f'<div class="notice {cls}">{escape(notice)}</div>'
    if error_message:
        notice_html = f'<div class="notice error">{escape(error_message)}</div>'

    body = f"""
    {_admin_nav()}
    <div class="user-center-heading">
        <div><h1>用户编辑中心</h1><p class="muted">用户ID {int(user_id)} · 用户名 {escape(str(user.get('username') or ''))}</p></div>
        <a href="/admin/members/list">← 返回用户列表</a>
    </div>
    {notice_html}
    <link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-admin-user-routes-l180-622868a952.css">
    <div class="user-center-grid">
      <main>
        <section class="card">
          <h2>基础资料</h2>
          <form method="post" action="/admin/users/{int(user_id)}">
            <input type="hidden" name="csrf_token" value="{escape(csrf)}">
            <div class="form-grid">
              <label>用户ID</label><div class="readonly">{int(user_id)}</div>
              <label>用户名</label><div class="readonly">{escape(str(user.get('username') or ''))}</div>
              <label for="phone">手机号</label><input id="phone" name="phone" maxlength="64" value="{escape(str(user.get('phone') or ''))}">
              <label for="email">邮箱</label><input id="email" name="email" maxlength="254" value="{escape(str(user.get('email') or ''))}">
              <label for="taobao_nick">淘宝昵称</label><input id="taobao_nick" name="taobao_nick" maxlength="128" value="{escape(str(user.get('taobao_nick') or ''))}">
              <label for="register_source">注册来源</label><select id="register_source" name="register_source">{_source_options(str(user.get('register_source') or ''))}</select>
              <label>注册时间</label><div class="readonly">{escape(str(user.get('created_at') or ''))}</div>
              <label>更新时间</label><div class="readonly">{escape(str(user.get('updated_at') or ''))}</div>
              <label>最近登录</label><div class="readonly">{escape(str(user.get('last_login_at') or '')) or '—'}</div>
            </div>
            <div class="actions-row"><button type="submit">保存资料并同步飞书</button></div>
          </form>
        </section>
        <section class="card">
          <div class="csp-r5-c010d819027f507d">
            <div><h2>登录/退出记录</h2><p class="muted">最近20条用户认证事件</p></div>
            <a href="/admin/operation-history?target_user_id={int(user_id)}&action_category=authentication">查看全部</a>
          </div>
          <div class="history-wrap"><table class="history-table"><thead><tr><th>时间</th><th>结果</th><th>事件</th><th>IP</th><th>浏览器</th><th>错误码</th><th>原因</th></tr></thead><tbody>{_history_rows(auth_history,'暂无登录或退出记录')}</tbody></table></div>
        </section>
        <section class="card">
          <div class="csp-r5-c010d819027f507d">
            <div><h2>管理员操作记录</h2><p class="muted">最近20条针对该用户的管理员操作</p></div>
            <a href="/admin/operation-history?target_user_id={int(user_id)}&actor_type=admin">查看全部</a>
          </div>
          <div class="history-wrap"><table class="history-table"><thead><tr><th>时间</th><th>结果</th><th>操作</th><th>IP</th><th>浏览器</th><th>错误码</th><th>原因</th></tr></thead><tbody>{_history_rows(admin_history,'暂无管理员操作记录')}</tbody></table></div>
        </section>
      </main>
      <aside>
        <section class="card">
          <h2>账号状态</h2>
          <p>当前状态：<strong class="{status_class}">{escape(status_label)}</strong>（{escape(status)}）</p>
          <p class="muted">禁用只影响账号登录和API鉴权，不删除Token和套餐记录。</p>
          <form method="post" action="/admin/users/{int(user_id)}/status" data-confirm="确认执行账号状态变更？">
            <input type="hidden" name="csrf_token" value="{escape(csrf)}">
            <input type="hidden" name="status" value="{escape(next_status)}">
            <button type="submit" class="{'button-danger' if next_status == 'disabled' else 'button-enable'}">{escape(next_label)}</button>
          </form>
        </section>
        <section class="card">
          <h2>安全与套餐</h2>
          <div class="summary-grid">
            <div class="summary-box"><b>Token总数</b><div>{int(tokens.get('total') or 0)}</div></div>
            <div class="summary-box"><b>有效Token</b><div>{int(tokens.get('active') or 0)}</div></div>
            <div class="summary-box"><b>禁用Token</b><div>{int(tokens.get('disabled') or 0)}</div></div>
          </div>
          <p><b>当前套餐：</b>{escape(str(current_sub.get('plan_code') or '未开通'))}</p>
          <p><b>套餐周期：</b>{escape(str(current_sub.get('start_time') or '—'))} 至 {escape(str(current_sub.get('expire_time') or '—'))}</p>
          <p><b>待生效套餐：</b><br>{scheduled_html}</p>
          <div class="actions-row">
            <a href="/admin/members?user_id={int(user_id)}">套餐操作</a>
            <a href="/admin/users/reset-password?user_id={int(user_id)}">重置密码</a>
          </div>
        </section>
      </aside>
    </div>
    """
    return _page("用户编辑中心", body), status_code


@admin_user_bp.route("/users/<int:user_id>", methods=["GET", "POST"])
def admin_user_detail(user_id: int):
    if not require_admin_session():
        return redirect("/admin/login")
    if request.method == "GET":
        return _render_detail(user_id)
    if not _valid_csrf():
        detail = get_admin_user_detail(user_id)
        _audit(
            target_user=(detail or {}).get("user"),
            action_code="admin.user_profile.update",
            action_name="修改用户资料",
            success=False,
            status_code=403,
            error_code="csrf_invalid",
            error_message="CSRF校验失败",
        )
        return _render_detail(user_id, error_message="请求已过期，请刷新页面后重试", status_code=403)

    payload = {
        "phone": request.form.get("phone", ""),
        "email": request.form.get("email", ""),
        "taobao_nick": request.form.get("taobao_nick", ""),
        "register_source": request.form.get("register_source", ""),
    }
    detail = get_admin_user_detail(user_id)
    target = (detail or {}).get("user")
    try:
        result = update_user_profile(user_id, payload)
    except UserNotFoundError as exc:
        _audit(target_user=target, action_code="admin.user_profile.update", action_name="修改用户资料", success=False, status_code=404, error_code=exc.code, error_message=str(exc), request_data=payload)
        return _render_detail(user_id, error_message=str(exc), status_code=404, form_values=payload)
    except UserProfileConflictError as exc:
        _audit(target_user=target, action_code="admin.user_profile.update", action_name="修改用户资料", success=False, status_code=409, error_code=exc.code, error_message=str(exc), request_data=payload)
        return _render_detail(user_id, error_message=str(exc), status_code=409, form_values=payload)
    except UserProfileValidationError as exc:
        _audit(target_user=target, action_code="admin.user_profile.update", action_name="修改用户资料", success=False, status_code=400, error_code=exc.code, error_message=str(exc), request_data=payload)
        return _render_detail(user_id, error_message=str(exc), status_code=400, form_values=payload)
    except Exception as exc:
        _audit(target_user=target, action_code="admin.user_profile.update", action_name="修改用户资料", success=False, status_code=500, error_code="database_error", error_message=str(exc), request_data=payload)
        return _render_detail(user_id, error_message="保存失败，请检查服务器日志", status_code=500, form_values=payload)

    _audit(
        target_user=result.get("user"),
        action_code="admin.user_profile.update",
        action_name="修改用户资料",
        success=True,
        status_code=200,
        before_data=result.get("before"),
        after_data=result.get("after"),
        request_data={"changed_fields": result.get("changed_fields", [])},
    )
    sync_result = sync_user_profile_to_feishu(user_id)
    sync_success = sync_result.get("status") != "failed"
    _audit(
        target_user=result.get("user"),
        action_code="admin.user_profile.feishu_sync",
        action_name="用户资料同步飞书",
        success=sync_success,
        status_code=200 if sync_success else 502,
        error_code="" if sync_success else "feishu_sync_failed",
        error_message=sync_result.get("error", ""),
        after_data=sync_result,
    )
    if sync_result.get("status") == "failed":
        return _notice_redirect(user_id, "本地资料已修改，但飞书同步失败，请检查连接后重新保存", "warning")
    if sync_result.get("status") == "disabled":
        return _notice_redirect(user_id, "资料修改成功；飞书同步当前未启用")
    return _notice_redirect(user_id, "资料修改成功，已同步飞书")


@admin_user_bp.post("/users/<int:user_id>/status")
def admin_user_status(user_id: int):
    if not require_admin_session():
        return redirect("/admin/login")
    if not _valid_csrf():
        return _render_detail(user_id, error_message="请求已过期，请刷新页面后重试", status_code=403)
    new_status = str(request.form.get("status") or "").strip().lower()
    detail = get_admin_user_detail(user_id)
    target = (detail or {}).get("user")
    action_code = "admin.user_status.disable" if new_status == "disabled" else "admin.user_status.enable"
    action_name = "禁用用户账号" if new_status == "disabled" else "启用用户账号"
    try:
        result = set_user_status(user_id, new_status)
    except UserProfileError as exc:
        status_code = 404 if isinstance(exc, UserNotFoundError) else 400
        _audit(target_user=target, action_code=action_code, action_name=action_name, success=False, status_code=status_code, error_code=exc.code, error_message=str(exc), request_data={"status": new_status})
        return _render_detail(user_id, error_message=str(exc), status_code=status_code)
    except Exception as exc:
        _audit(target_user=target, action_code=action_code, action_name=action_name, success=False, status_code=500, error_code="database_error", error_message=str(exc), request_data={"status": new_status})
        return _render_detail(user_id, error_message="状态修改失败，请检查服务器日志", status_code=500)

    _audit(target_user=result.get("user"), action_code=action_code, action_name=action_name, success=True, status_code=200, before_data=result.get("before"), after_data=result.get("after"), request_data={"status": new_status})
    sync_result = sync_user_profile_to_feishu(user_id)
    sync_success = sync_result.get("status") != "failed"
    _audit(target_user=result.get("user"), action_code="admin.user_profile.feishu_sync", action_name="用户状态同步飞书", success=sync_success, status_code=200 if sync_success else 502, error_code="" if sync_success else "feishu_sync_failed", error_message=sync_result.get("error", ""), after_data=sync_result)
    verb = "禁用" if new_status == "disabled" else "启用"
    if sync_result.get("status") == "failed":
        return _notice_redirect(user_id, f"账号已{verb}，但飞书同步失败", "warning")
    return _notice_redirect(user_id, f"账号已{verb}")
