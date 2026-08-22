# -*- coding: utf-8 -*-
from html import escape
import logging
import hmac
import secrets

from flask import Blueprint, jsonify, make_response, redirect, request, session

from config import ADMIN_IP_WHITELIST, ADMIN_PASSWORD, ADMIN_USERNAME, ENABLE_FEISHU_SYNC
from db_utils import (
    get_active_subscription,
    get_scheduled_subscriptions,
    get_user_by_id,
    list_active_plans,
    list_members,
    list_members_page,
    list_password_reset_requests,
    mark_password_reset_handled,
)
from services.member_service import (
    admin_reset_user_password,
    create_or_get_user,
    get_or_create_api_key,
    ACTION_LABELS,
    apply_subscription_action,
    cancel_scheduled_subscription,
)
from services.audit_service import record_operation
from services.audit_security import token_fingerprint
from services.web_security import LoginAttemptLimiter, client_ip
from services.admin_auth import (
    verify_admin_client_certificate_request,
    verify_admin_high_risk_confirmation,
    verify_admin_password,
)
from services.admin_captcha import issue_admin_captcha, render_admin_captcha_png, verify_admin_captcha
from services.admin_client_certificate import touch_certificate_use
from services.site_url import public_url
import config

admin_member_bp = Blueprint("admin_member", __name__)
_admin_login_limiter = LoginAttemptLimiter(
    max_failures=config.ADMIN_LOGIN_MAX_FAILURES,
    window_seconds=config.ADMIN_LOGIN_WINDOW_SECONDS,
    lock_seconds=config.ADMIN_LOGIN_LOCK_SECONDS,
    namespace="admin",
    require_redis=bool(config.REDIS_REQUIRED),
)



def _sync_user_to_feishu_safely(user_id: int, reason: str = "admin_action") -> None:
    """管理员开通/续费后即时同步飞书；失败不影响后台开通结果。"""
    if not ENABLE_FEISHU_SYNC:
        return
    try:
        from services.feishu_sync_service import sync_single_user_to_feishu
        result = sync_single_user_to_feishu(int(user_id))
        logging.info("[后台] 触发飞书单用户同步: user_id=%s reason=%s result=%s", user_id, reason, result)
    except Exception as e:
        logging.exception("[后台] 飞书单用户同步失败，不影响开通结果: user_id=%s reason=%s err=%s", user_id, reason, e)


@admin_member_bp.before_request
def restrict_admin_ip():
    """可选后台 IP 白名单。ADMIN_IP_WHITELIST 为空时不限制。"""
    if not ADMIN_IP_WHITELIST:
        return None
    remote_ip = client_ip()
    allowed = {ip.strip() for ip in ADMIN_IP_WHITELIST if ip.strip()}
    if remote_ip not in allowed:
        return "当前 IP 不允许访问后台", 403
    return None


def require_admin_session() -> bool:
    return session.get("admin_logged_in") is True


def _admin_csrf_token() -> str:
    """Return the administrator CSRF token, creating one for legacy sessions."""
    token = str(session.get("admin_csrf_token") or "")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token


def _valid_admin_csrf() -> bool:
    expected = str(session.get("admin_csrf_token") or "")
    supplied = str(request.form.get("csrf_token") or "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _run_feishu_registration_import():
    """Lazy import keeps normal admin page loading independent of the Feishu SDK."""
    from services.feishu_sync_service import sync_feishu_to_local

    return sync_feishu_to_local()


def _wants_json_response() -> bool:
    return "application/json" in str(request.headers.get("Accept") or "").lower()


_SUBSCRIPTION_AUDIT_CODES = {
    "open": "admin.subscription_activate",
    "renew": "admin.subscription_renew",
    "switch_now": "admin.subscription_switch_now",
    "switch_scheduled": "admin.subscription_switch_scheduled",
}


def _audit_admin_operation(
    *,
    target_user,
    action_category: str,
    action_code: str,
    action_name: str,
    success: bool,
    status_code: int,
    error_code: str = "",
    error_message: str = "",
    before_data=None,
    after_data=None,
    request_data=None,
    strict: bool = False,
):
    return record_operation(
        actor_type="admin",
        actor_id=None,
        actor_name=ADMIN_USERNAME,
        target_user=target_user,
        action_category=action_category,
        action_code=action_code,
        action_name=action_name,
        success=success,
        status_code=status_code,
        error_code=error_code,
        error_message=error_message,
        before_data=before_data or {},
        after_data=after_data or {},
        request_data=request_data or {},
        strict=strict,
    )


def _admin_nav() -> str:
    user_register_url = escape(public_url("/user/register"), quote=True)
    return f"""
    <nav class="admin-nav" aria-label="后台导航">
        <a href="/admin/members">套餐操作</a>
        <a href="/admin/members/list">用户列表</a>
        <a href="/admin/password-reset/list">找回密码申请</a>
        <a href="/admin/users/reset-password">重置用户密码</a>
        <a href="/admin/operation-history">操作历史</a>
        <a href="/admin/data-access-history">数据访问历史</a>
        <a href="/admin/api-docs">API文档管理</a>
        <a href="/admin/interface-tester">市场接口测试台</a>
        <a href="{user_register_url}" target="_blank" rel="noopener">用户注册页</a>
        <form method="post" action="/admin/logout" class="csp-r5-6b8b63d565c4986a"><button type="submit">退出登录</button></form>
    </nav>
    """

def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{escape(title)}</title>
        <link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-admin-member-routes-l173-9f62b2453c.css">
    </head>
    <body>{body}</body>
    </html>
    """

def _record_admin_auth_event(
    *, actor_type: str, actor_name: str, action_code: str, action_name: str,
    success: bool, status_code: int, error_code: str = "", error_message: str = "",
    request_data=None,
):
    try:
        return record_operation(
            actor_type=actor_type, actor_id=None, actor_name=actor_name, target_user=None,
            action_category="authentication", action_code=action_code,
            action_name=action_name, success=success, status_code=status_code,
            error_code=error_code, error_message=error_message, request_data=request_data or {},
        )
    except Exception:
        logging.exception("[管理员认证] 写入操作历史失败: action=%s", action_code)
        return "", False


@admin_member_bp.route("/captcha.png", methods=["GET"])
def admin_captcha_image():
    certificate = verify_admin_client_certificate_request()
    if not certificate.ok:
        return "管理员客户端证书验证失败", 403
    code = issue_admin_captcha(session)
    response = make_response(render_admin_captcha_png(code))
    response.mimetype = "image/png"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _admin_login_form(*, error_message: str = "", certificate=None) -> str:
    error_html = f"<p class='error'>{escape(error_message)}</p>" if error_message else ""
    user_login_url = escape(public_url("/user/login"), quote=True)
    user_register_url = escape(public_url("/user/register"), quote=True)
    device = ""
    if certificate and certificate.certificate:
        device = escape(str(certificate.certificate.get("device_name") or "已登记设备"))
    device_note = f"<p class='muted'>当前客户端证书设备：<b>{device}</b></p>" if device else ""
    return _page("后台登录", f"""
    <h2>股票数据平台后台登录</h2>
    {error_html}
    {device_note}
    <form method="post" id="adminLoginForm" autocomplete="on">
        <p>用户名：<input name="username" autocomplete="username" required></p>
        <p>密码：<input name="password" type="password" autocomplete="current-password" required></p>
        <div class="captcha-row csp-r5-3a3f840294200e8e" >
            <label>图形验证码：<input name="captcha" autocomplete="off" maxlength="8" required class="csp-r5-9db3c3232aabbe19"></label>
            <img id="adminCaptchaImage" src="/admin/captcha.png?t=0" alt="图形验证码" width="180" height="58" class="csp-r5-c96b1e89bc747943">
            <button type="button" id="refreshAdminCaptcha">刷新验证码</button>
        </div>
        <p class="muted">请手动输入图片中的数字和大小写字母。点击图片或“刷新验证码”可更换。</p>
        <p class="muted">后台还会验证本机已安装的项目管理员客户端证书，无需短信或第三方认证应用。</p>
        <button type="submit">登录</button>
    </form>
    <script src="/static/js/admin-login.js" defer></script>
    <p><a href="{user_login_url}">普通用户登录</a> | <a href="{user_register_url}">普通用户注册</a></p>
    """)


@admin_member_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    certificate = verify_admin_client_certificate_request()
    if not certificate.ok:
        _record_admin_auth_event(
            actor_type="anonymous", actor_name="",
            action_code="admin.auth.client_certificate_rejected", action_name="管理员客户端证书验证失败",
            success=False, status_code=403, error_code=certificate.code,
            error_message=certificate.message,
        )
        return _page(
            "客户端证书验证失败",
            "<h2 class='error'>管理员客户端证书验证失败</h2>"
            "<p>请使用安装了有效管理员证书的设备，通过专用后台域名访问。</p>"
            f"<p>错误代码：{escape(certificate.code)}</p>",
        ), 403

    if request.method == "GET":
        return _admin_login_form(certificate=certificate)

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password", "")
    captcha = request.form.get("captcha", "")
    login_key = f"{client_ip()}|{username.lower()}"
    if _admin_login_limiter.is_blocked(login_key):
        return _page("登录受限", "<h2 class='error'>登录失败次数过多，请稍后再试</h2>"), 429

    captcha_ok = verify_admin_captcha(session, captcha)
    credentials_ok = hmac.compare_digest(username, ADMIN_USERNAME) and verify_admin_password(password)
    if captcha_ok and credentials_ok:
        _admin_login_limiter.clear(login_key)
        cert_record = certificate.certificate or {}
        certificate_id = int(cert_record.get("id") or 0)
        if certificate_id:
            try:
                touch_certificate_use(certificate_id, ip_address=client_ip())
            except Exception:
                logging.exception("[管理员证书] 更新最后使用时间失败 certificate_id=%s", certificate_id)
        session.clear()
        session["admin_logged_in"] = True
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
        session["admin_certificate_id"] = certificate_id
        session["admin_certificate_fingerprint"] = str(cert_record.get("fingerprint_sha256") or "")
        _record_admin_auth_event(
            actor_type="admin", actor_name=ADMIN_USERNAME,
            action_code="admin.auth.login_success", action_name="管理员登录成功",
            success=True, status_code=302,
            request_data={"username": username, "certificate_id": certificate_id},
        )
        return redirect("/admin/members")

    _admin_login_limiter.record_failure(login_key)
    _record_admin_auth_event(
        actor_type="anonymous", actor_name=username,
        action_code="admin.auth.login_failed", action_name="管理员登录失败",
        success=False, status_code=401, error_code="invalid_credentials",
        error_message="用户名、密码或图形验证码错误", request_data={"username": username},
    )
    return _admin_login_form(error_message="用户名、密码或图形验证码错误", certificate=certificate), 401


@admin_member_bp.route("/logout", methods=["POST"])
def admin_logout():
    if session.get("admin_logged_in") is True:
        _record_admin_auth_event(
            actor_type="admin", actor_name=ADMIN_USERNAME,
            action_code="admin.auth.logout", action_name="管理员退出登录",
            success=True, status_code=302, request_data={"logout": True},
        )
    session.clear()
    return redirect("/admin/login")


@admin_member_bp.route("/members", methods=["GET"])
def admin_members_page():
    if not require_admin_session():
        return redirect("/admin/login")

    selected_user_id = (request.args.get("user_id") or "").strip()
    selected_user = None
    selected_user_html = ""

    if selected_user_id:
        try:
            selected_user = get_user_by_id(int(selected_user_id))
        except ValueError:
            selected_user = None

        if selected_user:
            current_sub = get_active_subscription(int(selected_user["id"]))
            scheduled_subs = get_scheduled_subscriptions(int(selected_user["id"]))
            current_text = "未开通"
            if current_sub:
                current_text = f"{escape(str(current_sub.get('plan_code') or ''))}，{escape(str(current_sub.get('start_time') or ''))} 至 {escape(str(current_sub.get('expire_time') or ''))}"
            scheduled_html = "<span class='muted'>无</span>"
            if scheduled_subs:
                scheduled_html = "<br>".join(
                    f"ID {item['id']}：{escape(str(item.get('plan_code') or ''))}，{escape(str(item.get('start_time') or ''))} 至 {escape(str(item.get('expire_time') or ''))}"
                    for item in scheduled_subs
                )
            selected_user_html = f"""
            <div class="csp-r5-63c8c00007a02498">
                <b>当前选择用户：</b>
                <table class="csp-r5-a33b8fc2ff778068">
                    <tr><th>用户ID</th><td>{selected_user.get('id') or ''}</td></tr>
                    <tr><th>用户名</th><td>{escape(str(selected_user.get('username') or ''))}</td></tr>
                    <tr><th>手机号</th><td>{escape(str(selected_user.get('phone') or ''))}</td></tr>
                    <tr><th>邮箱</th><td>{escape(str(selected_user.get('email') or ''))}</td></tr>
                    <tr><th>淘宝昵称</th><td>{escape(str(selected_user.get('taobao_nick') or ''))}</td></tr>
                    <tr><th>当前套餐</th><td>{current_text}</td></tr>
                    <tr><th>待生效套餐</th><td>{scheduled_html}</td></tr>
                </table>
            </div>
            """
        else:
            selected_user_html = f"""
            <div class="csp-r5-072e7ed6ac0f6047">
                未找到用户ID：{escape(selected_user_id)}，请检查后再开通。
            </div>
            """

    plans = list_active_plans()
    options = "".join(
        f'<option value="{escape(p["plan_code"])}">{escape(p["plan_name"])} - {escape(p["plan_code"])} - {p["duration_days"]}天</option>'
        for p in plans
    )

    username_value = escape(str(selected_user.get("username") or "")) if selected_user else ""
    phone_value = escape(str(selected_user.get("phone") or "")) if selected_user else ""
    email_value = escape(str(selected_user.get("email") or "")) if selected_user else ""
    taobao_value = escape(str(selected_user.get("taobao_nick") or "")) if selected_user else ""

    return _page("套餐开通", f"""
    <h2>用户套餐操作</h2>
    {_admin_nav()}
    <div class="csp-r5-847dd0e4a84eab40">
        <b>说明：</b>
        <p>管理员必须明确选择：首次开通、续费当前套餐、立即换套餐、到期后换套餐。</p>
        <p>立即换套餐会终止当前套餐；到期后换套餐会新增待生效套餐。系统不会自动折算退款或差价。</p>
        <p>如果用户已经自助注册，优先填写用户ID；未注册用户可按手机号/邮箱/淘宝昵称创建。</p>
    </div>
    {selected_user_html}
    <form method="post" action="/admin/members/open">
        <p>用户ID：<input name="user_id" value="{escape(selected_user_id)}" placeholder="用户已注册时优先填写"></p>
        <p>用户名称：<input name="username" value="{username_value}"></p>
        <p>手机号：<input name="phone" value="{phone_value}">（推荐填写，用于查重）</p>
        <p>邮箱：<input name="email" value="{email_value}"></p>
        <p>淘宝昵称：<input name="taobao_nick" value="{taobao_value}">（手机号没有时用它查重）</p>
        <p>淘宝/微信/QQ订单号：<input name="taobao_order_no"></p>
        <p>操作类型：
            <select name="action_type" required>
                <option value="open">首次开通</option>
                <option value="renew">续费当前套餐</option>
                <option value="switch_now">立即换套餐</option>
                <option value="switch_scheduled">到期后换套餐</option>
            </select>
        </p>
        <p>目标套餐：<select name="plan_code">{options}</select></p>
        <p>额外补偿天数：<input name="extra_days" type="number" min="0" max="3650" value="0"></p>
        <p><label><input class="csp-r5-210f3039d0c507ac" type="checkbox" name="cancel_scheduled" value="1" checked> 立即换套餐时取消全部待生效套餐</label></p>
        <p><label><input class="csp-r5-210f3039d0c507ac" type="checkbox" name="confirm_switch_now" value="1"> 我确认立即换套餐会终止当前套餐剩余权益</label></p>
        <details class="csp-r5-5f637108d76126a8">
            <summary class="csp-r5-8dcad2c901e3b1d6">立即换套餐服务器端二次确认（仅 action_type=switch_now 时必填）</summary>
            <p class="csp-r5-d40fdf9f3a63beb5">当前管理员密码：<input name="admin_password" type="password" autocomplete="current-password" placeholder="仅立即换套餐时填写"></p>
            <p class="csp-r5-17a8681612b7e0f8">确认文字：<input name="confirmation_text" autocomplete="off" placeholder="SWITCH NOW">（必须精确输入 <code>SWITCH NOW</code>）</p>
        </details>
        <p>实际收款金额，单位分：<input name="amount_cent" placeholder="例如 1990 表示19.90元"></p>
        <p>优惠名称：<input name="promo_name" placeholder="例如 新人实时月卡9.9"></p>
        <p>备注：<input name="remark" placeholder="建议写明续费/升级/降级原因"></p>
        <button type="submit">确认套餐操作</button>
    </form>
    """)


@admin_member_bp.route("/members/open", methods=["POST"])
def admin_open_member():
    if not require_admin_session():
        return redirect("/admin/login")

    user_id_text = (request.form.get("user_id") or "").strip()
    username = request.form.get("username") or None
    phone = request.form.get("phone") or None
    email = request.form.get("email") or None
    taobao_nick = request.form.get("taobao_nick") or None
    taobao_order_no = request.form.get("taobao_order_no") or None
    plan_code = request.form.get("plan_code") or None
    action_type = (request.form.get("action_type") or "").strip()
    extra_days_text = (request.form.get("extra_days") or "0").strip()
    cancel_scheduled = request.form.get("cancel_scheduled") == "1"
    confirm_switch_now = request.form.get("confirm_switch_now") == "1"
    admin_password = request.form.get("admin_password") or ""
    confirmation_text = request.form.get("confirmation_text") or ""
    amount_cent_text = request.form.get("amount_cent") or ""
    promo_name = request.form.get("promo_name") or None
    remark = request.form.get("remark") or None
    target_hint = {
        "id": int(user_id_text) if user_id_text.isdigit() else None,
        "username": username or "", "phone": phone or "", "email": email or "",
    }
    safe_request = {
        "user_id": user_id_text, "username": username, "phone": phone, "email": email,
        "taobao_nick": taobao_nick, "taobao_order_no": taobao_order_no,
        "plan_code": plan_code, "action_type": action_type, "extra_days": extra_days_text,
        "cancel_scheduled": cancel_scheduled, "confirm_switch_now": confirm_switch_now,
        "amount_cent": amount_cent_text, "promo_name": promo_name, "remark": remark,
    }
    action_code = _SUBSCRIPTION_AUDIT_CODES.get(action_type, "admin.subscription_invalid")
    action_name = ACTION_LABELS.get(action_type, "套餐操作")

    def validation_failure(message: str, status: int = 400):
        _audit_admin_operation(
            target_user=target_hint, action_category="membership", action_code=action_code,
            action_name=action_name, success=False, status_code=status,
            error_code="validation_error", error_message=message, request_data=safe_request,
        )
        return message, status

    if not plan_code:
        return validation_failure("必须选择套餐")
    if action_type not in ACTION_LABELS:
        return validation_failure("必须选择有效的操作类型")
    if action_type == "switch_now" and not confirm_switch_now:
        return validation_failure("立即换套餐前必须勾选确认终止当前套餐剩余权益")
    if action_type == "switch_now":
        confirmation = verify_admin_high_risk_confirmation(
            admin_password,
            confirmation_text,
            "SWITCH NOW",
        )
        if not confirmation.ok:
            _audit_admin_operation(
                target_user=target_hint,
                action_category="membership",
                action_code=action_code,
                action_name=action_name,
                success=False,
                status_code=403,
                error_code=confirmation.code,
                error_message=confirmation.message,
                request_data=safe_request,
            )
            return _page(
                "立即换套餐二次确认失败",
                f"<h2 class='error'>操作已拒绝：{escape(confirmation.message)}</h2>{_admin_nav()}",
            ), 403

    try:
        amount_cent = int(amount_cent_text) if amount_cent_text.strip() else None
        extra_days = int(extra_days_text or 0)
    except ValueError:
        return validation_failure("实际收款金额和额外补偿天数必须是整数")

    user = None
    before_data = {}
    try:
        if user_id_text:
            user = get_user_by_id(int(user_id_text))
            if not user:
                return validation_failure("用户ID不存在", 404)
        else:
            if not phone and not taobao_nick and not email:
                return validation_failure("未填写用户ID时，手机号、淘宝昵称、邮箱至少填写一个，避免重复建用户")
            user = create_or_get_user(username=username, phone=phone, email=email, taobao_nick=taobao_nick)
        target_hint = user
        before_data = {
            "current_subscription": get_active_subscription(int(user["id"])),
            "scheduled_subscriptions": get_scheduled_subscriptions(int(user["id"])),
        }
        token = get_or_create_api_key(int(user["id"]))
        sub = apply_subscription_action(
            user_id=int(user["id"]), plan_code=plan_code, action_type=action_type,
            taobao_order_no=taobao_order_no, amount_cent=amount_cent,
            promo_name=promo_name, remark=remark, extra_days=extra_days,
            cancel_scheduled=cancel_scheduled, operator_name=ADMIN_USERNAME,
        )
        _sync_user_to_feishu_safely(int(user["id"]), reason="admin_open_member")
    except ValueError as e:
        _audit_admin_operation(
            target_user=user or target_hint, action_category="membership", action_code=action_code,
            action_name=action_name, success=False, status_code=400,
            error_code="business_validation_error", error_message=str(e),
            before_data=before_data, request_data=safe_request,
        )
        return _page("操作失败", f"<h2 class='error'>操作失败：{escape(str(e))}</h2>{_admin_nav()}"), 400
    except Exception as e:
        logging.exception("[后台] 套餐操作失败: %s", e)
        _audit_admin_operation(
            target_user=user or target_hint, action_category="membership", action_code=action_code,
            action_name=action_name, success=False, status_code=500,
            error_code="internal_error", error_message=str(e), before_data=before_data,
            request_data=safe_request,
        )
        return _page("操作失败", f"<h2 class='error'>操作失败：{escape(str(e))}</h2>{_admin_nav()}"), 500

    _, audit_ok = _audit_admin_operation(
        target_user=user, action_category="membership", action_code=action_code,
        action_name=action_name, success=True, status_code=200,
        before_data=before_data, after_data=sub, request_data=safe_request,
    )
    audit_warning = "" if audit_ok else "<p class='error'>业务操作成功，但审计系统异常，请立即检查服务器日志。</p>"
    return _page("套餐操作成功", f"""
    <h2 class="ok">套餐操作成功</h2>
    {audit_warning}
    {_admin_nav()}
    <p>用户ID：{user["id"]}</p>
    <p>用户名：{escape(str(user.get("username") or ""))}</p>
    <p>手机号：{escape(str(user.get("phone") or ""))}</p>
    <p>邮箱：{escape(str(user.get("email") or ""))}</p>
    <p>淘宝昵称：{escape(str(user.get("taobao_nick") or ""))}</p>
    <p>操作：{escape(sub["action_label"])}</p>
    <p>套餐：{escape(sub["plan_name"])} ({escape(sub["plan_code"])})</p>
    <p>额外补偿天数：{sub.get("extra_days", 0)}</p>
    <p>开始时间：{escape(sub["start_time"])}</p>
    <p>到期时间：{escape(sub["expire_time"])}</p>
    <p>X-API-Token 已创建或保持有效。出于安全原因，后台不再显示完整凭证；请让用户在用户中心自行轮换并妥善保存。</p>
    """)


@admin_member_bp.route("/members/list", methods=["GET"])
def admin_members_list():
    if not require_admin_session():
        return redirect("/admin/login")

    try:
        page = max(1, int(request.args.get("page") or 1))
    except ValueError:
        page = 1
    try:
        page_size = max(10, min(int(request.args.get("page_size") or 50), 100))
    except ValueError:
        page_size = 50
    query = str(request.args.get("q") or "").strip()
    result_page = list_members_page(page=page, page_size=page_size, query=query)
    members = result_page["items"]
    rows = []
    for m in members:
        user_id = m.get("user_id") or ""
        token_short = m.get("token_display") or "未生成"

        user_status = str(m.get("user_status") or "")
        key_status = str(m.get("key_status") or "")
        if user_status != "active":
            interface_status = "账号禁用"
            status_class = "status-disabled"
        elif m.get("plan_code") and key_status == "active":
            interface_status = "已开通"
            status_class = "status-open"
        elif m.get("plan_code") and key_status != "active":
            interface_status = "Token禁用"
            status_class = "status-disabled"
        elif m.get("scheduled_plan_code"):
            interface_status = "待生效"
            status_class = "status-wait"
        else:
            interface_status = "未开通"
            status_class = "status-closed"

        open_text = "套餐操作" if (m.get("plan_code") or m.get("scheduled_plan_code")) else "首次开通"
        action_parts = [
            f'<a class="action-link" href="/admin/users/{user_id}">查看/编辑</a>',
            f'<a class="action-link" href="/admin/members?user_id={user_id}">{open_text}</a>',
            f'<a class="action-link" href="/admin/users/reset-password?user_id={user_id}">重置密码</a>',
        ]
        if m.get("scheduled_subscription_id"):
            scheduled_subscription_id = int(m.get("scheduled_subscription_id"))
            expected_cancel_text = f"CANCEL SUBSCRIPTION {scheduled_subscription_id}"
            action_parts.append(
                '<details class="csp-r5-e74fa60fb17e9340">'
                '<summary class="action-button action-button-danger csp-r5-9463ff4798ce317c" >取消待生效</summary>'
                f'<form class="inline-action-form csp-r5-ab86cce0e9af8373" method="post" action="/admin/members/subscriptions/{scheduled_subscription_id}/cancel" '
                '>'
                f'<input type="hidden" name="user_id" value="{user_id}">'
                '<input type="password" name="admin_password" autocomplete="current-password" required placeholder="当前管理员密码">'
                f'<input name="confirmation_text" autocomplete="off" required placeholder="{expected_cancel_text}">'
                f'<small class="muted">精确输入：<code>{expected_cancel_text}</code></small>'
                '<button class="action-button action-button-danger" type="submit" '
                'data-confirm="确认取消该待生效套餐？">确认取消</button></form></details>'
            )
        action_html = "".join(action_parts)

        def display(value) -> str:
            if value is None or str(value).strip() == "":
                return '<span class="empty-value">—</span>'
            return escape(str(value))

        rows.append(f"""
        <tr>
            <td class="col-id sticky-id">{user_id}</td>
            <td class="col-username sticky-username" title="{escape(str(m.get('username') or ''))}">{display(m.get('username'))}</td>
            <td class="col-phone">{display(m.get('phone'))}</td>
            <td class="col-email">{display(m.get('email'))}</td>
            <td class="col-taobao">{display(m.get('taobao_nick'))}</td>
            <td class="col-source">{display(m.get('register_source'))}</td>
            <td class="col-interface-status"><span class="status-badge {status_class}">{escape(interface_status)}</span></td>
            <td class="col-plan">{display(m.get('plan_code'))}</td>
            <td class="col-plan-type">{display(m.get('plan_type'))}</td>
            <td class="col-expire">{display(m.get('expire_time'))}</td>
            <td class="col-scheduled-plan">{display(m.get('scheduled_plan_code'))}</td>
            <td class="col-scheduled-time">{display(m.get('scheduled_start_time'))}</td>
            <td class="col-token" title="仅显示Token前缀和后4位"><span class="token-text">{display(token_short)}</span></td>
            <td class="col-actions sticky-actions"><div class="action-links">{action_html}</div></td>
        </tr>
        """)

    csrf_token = escape(_admin_csrf_token())
    return _page("用户列表", f"""
    <div class="member-list-page">
        <div class="member-list-heading">
            <div class="member-list-title-group">
                <h2>用户列表</h2>
                <span class="member-list-count">共 {result_page['total']} 位用户，第 {result_page['page']} / {result_page['pages']} 页</span>
            </div>
            <div class="member-list-actions">
                <form id="feishuRegistrationImportForm" method="post" action="/admin/members/import-feishu-registrations">
                    <input type="hidden" name="csrf_token" value="{csrf_token}">
                    <button id="feishuRegistrationImportButton" class="primary-action-button" type="submit">导入飞书新登记</button>
                </form>
                <span id="feishuImportStatus" class="muted" role="status" aria-live="polite"></span>
            </div>
        </div>
        {_admin_nav()}
        <form method="get" action="/admin/members/list" class="csp-r5-76cba065e9f6fa42">
            <input name="q" value="{escape(query)}" placeholder="搜索ID、用户名、手机号、邮箱或淘宝昵称" class="csp-r5-b252a5682cbc726c">
            <select name="page_size"><option value="20" {'selected' if page_size == 20 else ''}>20/页</option><option value="50" {'selected' if page_size == 50 else ''}>50/页</option><option value="100" {'selected' if page_size == 100 else ''}>100/页</option></select>
            <button type="submit">搜索</button><a href="/admin/members/list">清除</a>
        </form>
        <p class="table-scroll-tip">表格宽度超过窗口时，可在表格区域内左右滑动；ID、用户名和操作列会保持固定。</p>
        <div class="member-table-viewport" role="region" aria-label="用户列表，可左右滚动" tabindex="0">
            <table class="member-table">
                <thead>
                    <tr>
                        <th class="col-id sticky-id">ID</th>
                        <th class="col-username sticky-username">用户名</th>
                        <th class="col-phone">手机号</th>
                        <th class="col-email">邮箱</th>
                        <th class="col-taobao">淘宝昵称</th>
                        <th class="col-source">来源</th>
                        <th class="col-interface-status">接口状态</th>
                        <th class="col-plan">当前套餐</th>
                        <th class="col-plan-type">类型</th>
                        <th class="col-expire">当前到期</th>
                        <th class="col-scheduled-plan">待生效套餐</th>
                        <th class="col-scheduled-time">待生效时间</th>
                        <th class="col-token">Token</th>
                        <th class="col-actions sticky-actions">操作</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        <div class="csp-r5-9b59622e9fac1ac6">
            {f'<a class="btn" href="/admin/members/list?page={result_page["page"]-1}&page_size={page_size}&q={escape(query, quote=True)}">上一页</a>' if result_page['page'] > 1 else '<span class="muted">上一页</span>'}
            <span>第 {result_page['page']} / {result_page['pages']} 页</span>
            {f'<a class="btn" href="/admin/members/list?page={result_page["page"]+1}&page_size={page_size}&q={escape(query, quote=True)}">下一页</a>' if result_page['page'] < result_page['pages'] else '<span class="muted">下一页</span>'}
        </div>
    </div>
    <script>
    (() => {{
        const form = document.getElementById('feishuRegistrationImportForm');
        const button = document.getElementById('feishuRegistrationImportButton');
        const status = document.getElementById('feishuImportStatus');
        if (!form || !button || !status) return;

        form.addEventListener('submit', async (event) => {{
            event.preventDefault();
            const confirmed = window.confirm(
                '仅导入飞书会员表中“用户ID为空”的新登记记录。新账号将保持禁用且不会创建Token或套餐，必须由管理员审核后再开通。确认执行吗？'
            );
            if (!confirmed) return;

            button.disabled = true;
            button.textContent = '正在导入…';
            status.textContent = '正在连接飞书并核对新登记，请勿重复点击。';
            status.className = 'muted';
            let reloadScheduled = false;
            try {{
                const response = await fetch(form.action, {{
                    method: 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    headers: {{'Accept': 'application/json'}},
                    body: new FormData(form)
                }});
                const rawText = await response.text();
                let payload = {{}};
                try {{ payload = rawText ? JSON.parse(rawText) : {{}}; }} catch (parseError) {{
                    payload = {{message: rawText || ('HTTP ' + response.status)}};
                }}
                const message = payload.message || payload.msg || '导入请求已结束';
                if (!response.ok || !payload.success) {{
                    status.textContent = message;
                    status.className = 'error';
                    return;
                }}
                status.textContent = `${{message}}：新增${{payload.added_count || 0}}，关联${{payload.linked_count || 0}}。列表即将刷新。`;
                status.className = 'ok';
                reloadScheduled = true;
                window.setTimeout(() => window.location.reload(), 1200);
            }} catch (error) {{
                status.textContent = '导入请求失败：' + error;
                status.className = 'error';
            }} finally {{
                if (!reloadScheduled) {{
                    button.disabled = false;
                    button.textContent = '导入飞书新登记';
                }}
            }}
        }});
    }})();
    </script>
    """)


@admin_member_bp.route("/members/import-feishu-registrations", methods=["POST"])
def admin_import_feishu_registrations():
    if not require_admin_session():
        return redirect("/admin/login")

    audit_request = {"trigger": "admin_members_page"}
    action_code = "admin.feishu_registration_import"
    action_name = "导入飞书新登记"

    if not _valid_admin_csrf():
        _audit_admin_operation(
            target_user=None,
            action_category="membership",
            action_code=action_code,
            action_name=action_name,
            success=False,
            status_code=400,
            error_code="invalid_csrf",
            error_message="管理员请求校验失败",
            request_data=audit_request,
        )
        if _wants_json_response():
            return jsonify({
                "success": False, "status": "invalid_csrf",
                "message": "请求校验失败，请刷新页面后重试",
                "added_count": 0, "linked_count": 0,
            }), 400
        return _page(
            "导入失败",
            f"""
            <h2 class="error">请求校验失败</h2>
            {_admin_nav()}
            <div class="sync-result-card">
                <p>当前管理员会话已过期或请求来源无效，本次没有执行飞书导入。</p>
                <p><a href="/admin/members/list">返回用户列表</a></p>
            </div>
            """,
        ), 400

    try:
        result = _run_feishu_registration_import()
    except Exception as exc:
        logging.exception("[后台] 飞书新登记导入发生未处理异常: %s", exc)
        _audit_admin_operation(
            target_user=None,
            action_category="membership",
            action_code=action_code,
            action_name=action_name,
            success=False,
            status_code=500,
            error_code="internal_error",
            error_message="飞书新登记导入发生未处理异常",
            request_data=audit_request,
        )
        if _wants_json_response():
            return jsonify({
                "success": False, "status": "error",
                "message": "导入失败，请查看服务器日志",
                "added_count": 0, "linked_count": 0,
            }), 500
        return _page(
            "导入失败",
            f"""
            <h2 class="error">飞书新登记导入失败</h2>
            {_admin_nav()}
            <div class="sync-result-card">
                <p>导入失败，请查看服务器日志。</p>
                <p><a href="/admin/members/list">返回用户列表</a></p>
            </div>
            """,
        ), 500

    counts_value = getattr(result, "counts", None)
    if counts_value is None:
        counts_value = tuple(result) if result is not None else (0, 0)
    counts = tuple(counts_value)
    added_count = int(counts[0]) if len(counts) >= 1 else 0
    linked_count = int(counts[1]) if len(counts) >= 2 else 0
    status = str(getattr(result, "status", "ok") or "ok")
    raw_message = str(getattr(result, "message", "") or "")

    status_map = {
        "ok": (200, True, "ok", "飞书新登记导入完成", raw_message or "飞书登记导入完成"),
        "empty": (200, True, "ok", "没有需要导入的新登记", raw_message or "飞书会员表没有可导入记录"),
        "busy": (409, False, "error", "本次导入未执行", "其他飞书同步任务正在运行，请稍后重试。"),
        "database_busy": (503, False, "error", "本次导入未完成", "数据库正在处理其他写入任务，请稍后重试。"),
        "schema_not_ready": (503, False, "error", "本次导入未完成", "数据库尚未完成启动初始化，请检查服务启动状态。"),
        "skipped": (503, False, "error", "本次导入已跳过", raw_message or "飞书同步未启用或配置不完整。"),
        "error": (500, False, "error", "飞书新登记导入失败", "导入失败，请查看服务器日志。"),
    }
    http_status, success, title_class, heading, display_message = status_map.get(
        status,
        (500, False, "error", "飞书新登记导入失败", "导入失败，请查看服务器日志。"),
    )

    status_labels = {
        "ok": "成功",
        "empty": "无新记录",
        "busy": "同步任务繁忙",
        "database_busy": "数据库繁忙",
        "schema_not_ready": "数据库未初始化",
        "skipped": "已跳过",
        "error": "失败",
    }
    status_label = status_labels.get(status, "失败")
    audit_error_message = "" if success else display_message
    try:
        _, audit_ok = _audit_admin_operation(
            target_user=None,
            action_category="membership",
            action_code=action_code,
            action_name=action_name,
            success=success,
            status_code=http_status,
            error_code="" if success else status,
            error_message=audit_error_message,
            after_data={
                "status": status,
                "added_count": added_count,
                "linked_count": linked_count,
            },
            request_data=audit_request,
        )
    except Exception:
        logging.exception("[后台] 飞书新登记导入审计写入失败: status=%s", status)
        audit_ok = False

    audit_warning = "" if audit_ok else '<p class="error">导入结果已产生，但审计系统异常，请立即检查服务器日志。</p>'
    if _wants_json_response():
        response = jsonify({
            "success": success,
            "status": status,
            "message": display_message,
            "added_count": added_count,
            "linked_count": linked_count,
        })
        response.headers["Cache-Control"] = "no-store"
        return response, http_status
    return _page(
        heading,
        f"""
        <h2 class="{title_class}">{escape(heading)}</h2>
        {_admin_nav()}
        <div class="sync-result-card">
            <p>{escape(display_message)}</p>
            <p><b>新增本地用户：{added_count}</b></p>
            <p><b>关联已有用户：{linked_count}</b></p>
            <p><b>执行状态：</b>{escape(status_label)}</p>
            {audit_warning}
            <p class="muted">本操作只处理飞书会员表中用户ID为空的新登记；新增账号保持禁用且不会创建Token或套餐，必须由管理员审核后再开通，也不会从飞书覆盖已有用户资料。</p>
            <p><a href="/admin/members/list">返回用户列表</a></p>
        </div>
        """,
    ), http_status


@admin_member_bp.route("/members/subscriptions/<int:subscription_id>/cancel", methods=["POST"])
def admin_cancel_scheduled_subscription(subscription_id: int):
    if not require_admin_session():
        return redirect("/admin/login")
    user_id_text = (request.form.get("user_id") or "").strip()
    admin_password = request.form.get("admin_password") or ""
    confirmation_text = request.form.get("confirmation_text") or ""
    target = get_user_by_id(int(user_id_text)) if user_id_text.isdigit() else None
    request_data = {"user_id": user_id_text, "subscription_id": subscription_id}
    if not user_id_text.isdigit():
        _audit_admin_operation(
            target_user=target, action_category="membership",
            action_code="admin.subscription_switch_cancel", action_name="取消待生效套餐",
            success=False, status_code=400, error_code="validation_error",
            error_message="用户ID无效", request_data=request_data,
        )
        return "用户ID无效", 400
    confirmation = verify_admin_high_risk_confirmation(
        admin_password,
        confirmation_text,
        f"CANCEL SUBSCRIPTION {int(subscription_id)}",
    )
    if not confirmation.ok:
        _audit_admin_operation(
            target_user=target,
            action_category="membership",
            action_code="admin.subscription_switch_cancel",
            action_name="取消待生效套餐",
            success=False,
            status_code=403,
            error_code=confirmation.code,
            error_message=confirmation.message,
            request_data=request_data,
        )
        return _page(
            "取消待生效套餐二次确认失败",
            f"<h2 class='error'>操作已拒绝：{escape(confirmation.message)}</h2>{_admin_nav()}",
        ), 403
    try:
        before = cancel_scheduled_subscription(int(user_id_text), int(subscription_id), operator_name=ADMIN_USERNAME)
        _sync_user_to_feishu_safely(int(user_id_text), reason="admin_cancel_scheduled")
    except ValueError as e:
        _audit_admin_operation(
            target_user=target, action_category="membership",
            action_code="admin.subscription_switch_cancel", action_name="取消待生效套餐",
            success=False, status_code=400, error_code="business_validation_error",
            error_message=str(e), request_data=request_data,
        )
        return _page("取消失败", f"<h2 class='error'>取消失败：{escape(str(e))}</h2>{_admin_nav()}"), 400
    _audit_admin_operation(
        target_user=target, action_category="membership",
        action_code="admin.subscription_switch_cancel", action_name="取消待生效套餐",
        success=True, status_code=200, before_data=before,
        after_data={"subscription_id": subscription_id, "status": "cancelled"},
        request_data=request_data,
    )
    return redirect("/admin/members/list")


@admin_member_bp.route("/users/reset-password", methods=["GET", "POST"])
def admin_reset_password_page():
    if not require_admin_session():
        return redirect("/admin/login")

    if request.method == "GET":
        user_id = request.args.get("user_id", "")
        return _page("重置用户密码", f"""
        <h2>重置用户密码</h2>
        {_admin_nav()}
        <form method="post">
            <p>用户ID：<input name="user_id" value="{escape(user_id)}" required></p>
            <p>新密码：<input name="new_password" type="password" required placeholder="至少6位"></p>
            <p>确认新密码：<input name="new_password2" type="password" required></p>
            <p>管理员当前密码：<input name="admin_password" type="password" required autocomplete="current-password"></p>
            <p>高风险确认：请输入 <code>RESET USER PASSWORD</code>：<input name="confirmation_text" required autocomplete="off"></p>
            <p>找回申请ID，可选：<input name="reset_request_id" placeholder="处理找回申请时填写"></p>
            <p>处理备注，可选：<input name="admin_remark" placeholder="例如 已微信通知用户"></p>
            <button type="submit">确认重置</button>
        </form>
        """)

    user_id = request.form.get("user_id", "").strip()
    new_password = request.form.get("new_password", "")
    new_password2 = request.form.get("new_password2", "")
    admin_password = request.form.get("admin_password", "")
    confirmation_text = request.form.get("confirmation_text", "")
    reset_request_id = request.form.get("reset_request_id", "").strip()
    admin_remark = request.form.get("admin_remark", "")
    target = get_user_by_id(int(user_id)) if user_id.isdigit() else None
    safe_request = {
        "user_id": user_id, "reset_request_id": reset_request_id,
        "admin_remark": admin_remark, "password_changed": False,
    }

    if new_password != new_password2:
        _audit_admin_operation(
            target_user=target, action_category="account",
            action_code="admin.user_password_reset", action_name="管理员重置用户密码",
            success=False, status_code=400, error_code="password_confirmation_mismatch",
            error_message="两次密码不一致", request_data=safe_request,
        )
        return _page("重置失败", f"<h2 class='error'>两次密码不一致</h2>{_admin_nav()}"), 400

    confirmation = verify_admin_high_risk_confirmation(
        admin_password,
        confirmation_text,
        "RESET USER PASSWORD",
    )
    if not confirmation.ok:
        _audit_admin_operation(
            target_user=target, action_category="account",
            action_code="admin.user_password_reset", action_name="管理员重置用户密码",
            success=False, status_code=403, error_code=confirmation.code,
            error_message=confirmation.message, request_data=safe_request,
        )
        return _page(
            "重置失败",
            f"<h2 class='error'>{escape(confirmation.message)}</h2>{_admin_nav()}",
        ), 403

    try:
        user = admin_reset_user_password(int(user_id), new_password)
        if reset_request_id:
            mark_password_reset_handled(int(reset_request_id), admin_remark or "已重置密码")
    except Exception as e:
        _audit_admin_operation(
            target_user=target, action_category="account",
            action_code="admin.user_password_reset", action_name="管理员重置用户密码",
            success=False, status_code=400, error_code="password_reset_failed",
            error_message=str(e), request_data=safe_request,
        )
        return _page("重置失败", f"<h2 class='error'>重置失败：{escape(str(e))}</h2>{_admin_nav()}"), 400

    safe_request["password_changed"] = True
    _, audit_ok = _audit_admin_operation(
        target_user=user, action_category="account",
        action_code="admin.user_password_reset", action_name="管理员重置用户密码",
        success=True, status_code=200,
        before_data={"password_changed": False}, after_data={"password_changed": True},
        request_data={"password_changed": True},
    )
    warning = "" if audit_ok else "<p class='error'>密码已重置，但审计系统异常，请立即检查服务器日志。</p>"
    return _page("重置成功", f"""
    <h2 class="ok">密码重置成功</h2>
    {warning}
    {_admin_nav()}
    <p>用户ID：{user['id']}</p>
    <p>用户名：{escape(str(user.get('username') or ''))}</p>
    <p>新密码已经生效，请通过微信/QQ/其他渠道告知用户。</p>
    """)


@admin_member_bp.route("/password-reset/list", methods=["GET"])
def admin_password_reset_list():
    if not require_admin_session():
        return redirect("/admin/login")

    requests = list_password_reset_requests()
    rows = []
    for r in requests:
        user_id = r.get("user_id") or ""
        reset_link = f"/admin/users/reset-password?user_id={user_id}" if user_id else "/admin/users/reset-password"
        rows.append(f"""
        <tr>
            <td>{r.get('id') or ''}</td>
            <td>{escape(str(user_id))}</td>
            <td>{escape(str(r.get('account') or ''))}</td>
            <td>{escape(str(r.get('contact') or ''))}</td>
            <td>{escape(str(r.get('username') or ''))}</td>
            <td>{escape(str(r.get('phone') or ''))}</td>
            <td>{escape(str(r.get('email') or ''))}</td>
            <td>{escape(str(r.get('status') or ''))}</td>
            <td>{escape(str(r.get('created_at') or ''))}</td>
            <td>{escape(str(r.get('handled_at') or ''))}</td>
            <td><a href="{reset_link}">重置密码</a></td>
        </tr>
        """)

    return _page("找回密码申请", f"""
    <h2>找回密码申请</h2>
    {_admin_nav()}
    <table>
        <tr>
            <th>申请ID</th><th>用户ID</th><th>账号</th><th>联系方式</th>
            <th>用户名</th><th>手机号</th><th>邮箱</th><th>状态</th>
            <th>申请时间</th><th>处理时间</th><th>操作</th>
        </tr>
        {''.join(rows)}
    </table>
    """)
