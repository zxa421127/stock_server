# -*- coding: utf-8 -*-
"""
普通用户注册、登录、用户中心、自助找回密码。

第一版逻辑：
- 用户可以自助注册和登录。
- 注册后自动生成 X-API-Token，但不自动开通套餐，所以接口调用会提示联系管理员。
- 找回密码支持用户通过账号 + 注册手机号/邮箱自助修改密码。
- 用户中心提供常用接入代码，方便用户复制到自己的项目里调用接口。
"""
from html import escape
import logging
import re
import secrets

import config

from flask import Blueprint, jsonify, make_response, redirect, request, session

from config import CONTACT_NOTE, CONTACT_QQ, CONTACT_WECHAT, ENABLE_FEISHU_SYNC
from db_utils import (
    get_active_api_key,
    get_active_subscription,
    get_plan_by_code,
    get_scheduled_subscriptions,
    get_user_by_account,
    get_user_by_id,
    list_membership_actions,
)
from services.api_doc_service import get_api_doc_statistics, list_public_docs
from services.api_doc_runtime_status import endpoint_identity_from_path
from services.member_service import (
    authenticate_user,
    change_user_password,
    get_or_create_api_key,
    hash_password,
    register_user,
    register_verified_user,
    rotate_api_key,
    verify_password,
    submit_password_reset_request,
)
from services.audit_service import record_operation
from services.site_url import admin_url

from services.web_security import AttemptLimiter, LoginAttemptLimiter, client_ip
from services.captcha_service import issue_captcha, verify_captcha
from services.admin_captcha import render_admin_captcha_png
from services.contact_verification import create_challenge, mark_delivery_failed, verify_and_consume_challenge
from services.notification_delivery import send_email_code, send_sms_code
from services.user_input_security import normalize_registration_input, validate_login_input, validate_password_reset_input

user_bp = Blueprint("user", __name__)
_user_login_limiter = LoginAttemptLimiter(
    max_failures=config.USER_LOGIN_MAX_FAILURES,
    window_seconds=config.USER_LOGIN_WINDOW_SECONDS,
    lock_seconds=config.USER_LOGIN_LOCK_SECONDS,
    namespace="user",
    require_redis=bool(config.REDIS_REQUIRED),
)
_registration_limiter = AttemptLimiter(
    max_attempts=config.USER_REGISTRATION_MAX_REQUESTS,
    window_seconds=config.USER_REGISTRATION_WINDOW_SECONDS,
    lock_seconds=config.USER_REGISTRATION_LOCK_SECONDS,
    namespace="registration-ip",
    require_redis=bool(config.REDIS_REQUIRED),
)
_registration_global_limiter = AttemptLimiter(
    max_attempts=config.REGISTRATION_GLOBAL_MAX_REQUESTS,
    window_seconds=config.REGISTRATION_GLOBAL_WINDOW_SECONDS,
    lock_seconds=config.REGISTRATION_GLOBAL_LOCK_SECONDS,
    namespace="registration-global",
    require_redis=bool(config.REDIS_REQUIRED),
)
_password_reset_limiter = LoginAttemptLimiter(
    max_failures=config.PASSWORD_RESET_MAX_REQUESTS,
    window_seconds=config.PASSWORD_RESET_WINDOW_SECONDS,
    lock_seconds=config.PASSWORD_RESET_LOCK_SECONDS,
    namespace="password-reset",
    require_redis=bool(config.REDIS_REQUIRED),
)



def _sync_user_to_feishu_safely(user_id: int, reason: str = "user_action") -> None:
    """用户注册/资料变化后即时同步飞书；失败不影响前端业务流程。"""
    if not ENABLE_FEISHU_SYNC:
        return
    try:
        from services.feishu_sync_service import sync_single_user_to_feishu
        result = sync_single_user_to_feishu(int(user_id))
        logging.info("[用户] 触发飞书单用户同步: user_id=%s reason=%s result=%s", user_id, reason, result)
    except Exception as e:
        logging.exception("[用户] 飞书单用户同步失败，不影响用户流程: user_id=%s reason=%s err=%s", user_id, reason, e)


def _contact_html() -> str:
    """按 .env 配置动态显示联系方式。

    规则：
    - 只配置 QQ：只显示 QQ
    - 只配置微信：只显示微信
    - 两个都配置：两个都显示
    - 两个都没配置：整个联系方式区域不显示
    """
    rows = []
    if CONTACT_QQ:
        rows.append(f"<li>QQ：{escape(CONTACT_QQ)}</li>")
    if CONTACT_WECHAT:
        rows.append(f"<li>微信：{escape(CONTACT_WECHAT)}</li>")
    if not rows:
        return ""

    return f"""
    <div class="csp-r5-de2559a35f6ebd14">
        <b>开通接口说明</b>
        <p>{escape(CONTACT_NOTE)}</p>
        <ul>{''.join(rows)}</ul>
    </div>
    """


def _page(title: str, body: str) -> str:
    admin_login_url = escape(admin_url("/admin/login"), quote=True)
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{escape(title)}</title>
        <link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-user-routes-l131-7bfed51700.css">
    </head>
    <body>
        <p>
            <a href="/user/dashboard">用户中心</a> |
            <a href="/user/login">用户登录</a> |
            <a href="/user/register">用户注册</a> |
            <a href="/user/forgot-password">找回密码</a> |
            <a href="/user/api-docs">平台API接口</a> |
            <a href="{admin_login_url}">管理员后台</a>
        </p>
        {body}
    </body>
    </html>
    """


def _establish_user_session(user: dict) -> None:
    session.clear()
    session["user_id"] = int(user["id"])
    session["user_session_version"] = int(user.get("session_version") or 1)
    session["user_csrf_token"] = secrets.token_urlsafe(32)


def _registration_attempt_allowed() -> bool:
    ip_key = f"{client_ip()}|registration"
    ip_allowed = _registration_limiter.check_and_record(ip_key)
    global_allowed = _registration_global_limiter.check_and_record("registration-global")
    return bool(ip_allowed and global_allowed)


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_user_by_id(int(user_id))
    if user and str(user.get("status") or "") == "active":
        current_version = int(user.get("session_version") or 1)
        supplied_version = session.get("user_session_version")
        if supplied_version is None and str(getattr(config, "APP_ENV", "development")).lower() != "production":
            session["user_session_version"] = current_version
            return user
        try:
            if int(supplied_version) == current_version:
                return user
        except (TypeError, ValueError):
            pass

    session.clear()
    target_user = user or {"id": int(user_id)}
    record_operation(
        actor_type="user",
        actor_id=int(user_id),
        actor_name=str((user or {}).get("username") or ""),
        target_user=target_user,
        action_category="authentication",
        action_code="user.auth.session_rejected",
        action_name="用户会话被拒绝",
        success=False,
        status_code=401,
        error_code="account_disabled" if user else "account_missing",
        error_message="用户账号不可用，已清除登录会话",
        request_data={"session_cleared": True},
    )
    return None


def _api_integration_html(token: str, base_url: str) -> str:
    """用户中心展示当前唯一正式接入路径。"""
    safe_token = token or ""
    base_url = (base_url or "").rstrip("/")
    example_url = f"{base_url}/api/v1/market/tushare/stock_basic?list_status=L"

    curl_code = f"""curl -X GET "{example_url}" ^
  -H "X-API-Token: {safe_token}"""

    python_code = f"""import requests

TOKEN = "{safe_token}"
BASE_URL = "{base_url}"

resp = requests.get(
    f"{{BASE_URL}}/api/v1/market/tushare/stock_basic",
    params={{"list_status": "L"}},
    headers={{"X-API-Token": TOKEN}},
    timeout=30,
)
print(resp.status_code)
print(resp.json())
"""

    js_code = f"""const TOKEN = "{safe_token}";
const BASE_URL = "{base_url}";

fetch(`${{BASE_URL}}/api/v1/market/tushare/stock_basic?list_status=L`, {{
  headers: {{"X-API-Token": TOKEN}}
}})
  .then(res => res.json())
  .then(console.log);
"""

    return f"""
    <div class="api-box">
        <h3>用户接入数据代码</h3>
        <p class="muted">正式接口统一使用 <code>/api/v1/market/tushare/&lt;api_name&gt;</code>，并在请求头携带 <b>X-API-Token</b>。</p>
        <table class="endpoint-table">
            <tr><th>项目</th><th>内容</th></tr>
            <tr><td>接口域名</td><td><code>{escape(base_url)}</code></td></tr>
            <tr><td>请求头</td><td><code>X-API-Token: {escape(safe_token)}</code></td></tr>
            <tr><td>接口目录</td><td><code>/api/v1/market/tushare/catalog</code></td></tr>
            <tr><td>股票列表</td><td><code>/api/v1/market/tushare/stock_basic?list_status=L</code></td></tr>
            <tr><td>交易日历</td><td><code>/api/v1/market/tushare/trade_cal?exchange=SSE&amp;start_date=20260701&amp;end_date=20260731</code></td></tr>
            <tr><td>实时行情</td><td><code>/api/v1/market/tushare/rt_k?ts_code=000001.SZ</code>（需实时套餐）</td></tr>
        </table>
        <details open><summary>Windows CMD / curl</summary><pre><code>{escape(curl_code)}</code></pre></details>
        <details><summary>Python requests</summary><pre><code>{escape(python_code)}</code></pre></details>
        <details><summary>JavaScript fetch</summary><pre><code>{escape(js_code)}</code></pre></details>
    </div>
    """


@user_bp.get("/register/captcha.png")
def registration_captcha_image():
    code = issue_captcha(
        session,
        "registration",
        length=int(getattr(config, "REGISTRATION_CAPTCHA_LENGTH", 5)),
    )
    response = make_response(render_admin_captcha_png(code))
    response.headers["Content-Type"] = "image/png"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _registration_channel_options() -> str:
    options = []
    if bool(getattr(config, "REGISTRATION_EMAIL_VERIFICATION_ENABLED", True)):
        options.append('<option value="email">邮箱验证码</option>')
    if bool(getattr(config, "REGISTRATION_SMS_VERIFICATION_ENABLED", False)):
        options.append('<option value="sms">手机短信验证码</option>')
    return "".join(options)


def _registration_form_html() -> str:
    verification_required = bool(getattr(config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", False))
    verification_html = ""
    if verification_required:
        options = _registration_channel_options()
        if options:
            verification_html = f"""
            <p>验证方式：<select name="verification_channel" required>{options}</select></p>
            <p>图形验证码：<input name="captcha" maxlength="8" required autocomplete="off"></p>
            <p><img id="registration-captcha" src="/user/register/captcha.png?t=0" alt="图形验证码" width="180" height="58"
                class="csp-r5-4defed6029562c15" title="点击刷新验证码"></p>
            <script src="/static/user_register.js" defer></script>
            """
        else:
            verification_html = "<p class='error'>注册验证服务尚未配置，请联系管理员。</p>"
    return f"""
        <h2>用户注册</h2>
        <p class="muted">注册后默认是普通用户；接口套餐需要联系管理员付款后开通。</p>
        <form method="post">
            <p>用户名：<input name="username" required maxlength="{config.USER_USERNAME_MAX_LENGTH}" placeholder="{config.USER_USERNAME_MIN_LENGTH}-{config.USER_USERNAME_MAX_LENGTH}个字符"></p>
            <p>密码：<input name="password" type="password" required maxlength="{config.USER_PASSWORD_MAX_LENGTH}" placeholder="{config.USER_PASSWORD_MIN_LENGTH}-{config.USER_PASSWORD_MAX_LENGTH}位"></p>
            <p>确认密码：<input name="password2" type="password" required maxlength="{config.USER_PASSWORD_MAX_LENGTH}"></p>
            <p>手机号：<input name="phone" maxlength="{config.USER_PHONE_MAX_LENGTH}" placeholder="手机号或邮箱至少填一个"></p>
            <p>邮箱：<input name="email" maxlength="{config.USER_EMAIL_MAX_LENGTH}" placeholder="手机号或邮箱至少填一个"></p>
            {verification_html}
            <button type="submit">提交注册</button>
        </form>
        <p>已有账号？<a href="/user/login">去登录</a></p>
        {_contact_html()}
    """


@user_bp.route("/register", methods=["GET", "POST"])
def user_register():
    verification_required = bool(getattr(config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", False))
    if request.method == "GET":
        return _page("用户注册", _registration_form_html())

    if verification_required and not _registration_attempt_allowed():
        return _page("注册受限", "<h2 class='error'>注册请求过于频繁，请稍后再试</h2>"), 429

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    password2 = request.form.get("password2", "")
    phone = request.form.get("phone", "")
    email = request.form.get("email", "")
    safe_input = {"username": username, "phone": phone, "email": email}
    target_hint = {"id": None, "username": username, "phone": phone, "email": email}

    if verification_required:
        captcha_ok = verify_captcha(
            session,
            "registration",
            request.form.get("captcha", ""),
            ttl_seconds=int(getattr(config, "REGISTRATION_CAPTCHA_TTL_SECONDS", 300)),
        )
        if not captcha_ok:
            record_operation(
                actor_type="anonymous", actor_id=None, actor_name=str(username).strip(), target_user=target_hint,
                action_category="account", action_code="user.register.captcha_failed",
                action_name="用户注册图形验证码失败", success=False, status_code=400,
                error_code="invalid_captcha", error_message="图形验证码错误或已过期", request_data=safe_input,
            )
            return _page("注册失败", "<h2 class='error'>图形验证码错误或已过期</h2><p><a href='/user/register'>返回注册</a></p>"), 400

    if password != password2:
        record_operation(
            actor_type="user", actor_id=None, actor_name=username, target_user=target_hint,
            action_category="account", action_code="user.register", action_name="用户注册",
            success=False, status_code=400, error_code="password_confirmation_mismatch",
            error_message="两次密码不一致", request_data=safe_input,
        )
        return _page("注册失败", "<h2 class='error'>注册失败：两次密码不一致</h2><p><a href='/user/register'>返回注册</a></p>"), 400

    try:
        if not verification_required:
            user, token = register_user(
                username=username,
                password=password,
                phone=phone,
                email=email,
            )
            normalized = type("RegistrationAuditInput", (), {
                "username": str(username).strip(),
                "phone": str(phone).strip() or None,
                "email": str(email).strip().lower() or None,
            })()
            safe_input = {"username": normalized.username, "phone": normalized.phone, "email": normalized.email}
            _establish_user_session(user)
            _sync_user_to_feishu_safely(int(user["id"]), reason="user_register")
            _, audit_ok = record_operation(
                actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or normalized.username),
                target_user=user, action_category="account", action_code="user.register",
                action_name="用户注册", success=True, status_code=200,
                before_data={}, after_data={"registered": True, "register_source": user.get("register_source") or "self"},
                request_data=safe_input,
            )
            audit_warning = "" if audit_ok else "<p class='error'>注册成功，但审计系统异常，请管理员检查服务器日志。</p>"
            return _page("注册成功", f"""
                <h2 class="ok">注册成功</h2>{audit_warning}
                <p>用户ID：{user['id']}</p>
                <p>用户名：{escape(str(user.get('username') or ''))}</p>
                <p>你的 X-API-Token：</p><textarea rows="3" readonly>{escape(token)}</textarea>
                <p><a href="/user/dashboard">进入用户中心</a></p>
            """)

        normalized = normalize_registration_input(
            username=username, password=password, phone=phone, email=email
        )
        safe_input = {"username": normalized.username, "phone": normalized.phone, "email": normalized.email}
        target_hint = {"id": None, **safe_input}
        if get_user_by_account(normalized.username):
            raise ValueError("用户名已存在")
        if normalized.phone and get_user_by_account(normalized.phone):
            raise ValueError("手机号已被注册")
        if normalized.email and get_user_by_account(normalized.email):
            raise ValueError("邮箱已被注册")

        channel = str(request.form.get("verification_channel", "") or "").strip().lower()
        if channel == "email":
            if not bool(getattr(config, "REGISTRATION_EMAIL_VERIFICATION_ENABLED", True)):
                raise ValueError("邮箱验证码注册未启用")
            if not normalized.email:
                raise ValueError("选择邮箱验证时必须填写邮箱")
            target = normalized.email
        elif channel == "sms":
            if not bool(getattr(config, "REGISTRATION_SMS_VERIFICATION_ENABLED", False)):
                raise ValueError("短信验证码注册未启用")
            if not normalized.phone:
                raise ValueError("选择短信验证时必须填写手机号")
            target = normalized.phone
        else:
            raise ValueError("请选择可用的验证方式")

        challenge = create_challenge(
            purpose="registration",
            channel=channel,
            target=target,
            payload={
                "username": normalized.username,
                "password_hash": hash_password(normalized.password),
                "phone": normalized.phone,
                "email": normalized.email,
            },
        )
        try:
            if channel == "email":
                send_email_code(target, challenge.code)
            else:
                send_sms_code(target, challenge.code)
        except Exception as delivery_error:
            mark_delivery_failed(challenge.challenge_id, str(delivery_error))
            logging.exception("[用户] 注册验证码发送失败 channel=%s", channel)
            raise RuntimeError("验证码发送失败，请稍后重试") from delivery_error
        session["registration_challenge_id"] = challenge.challenge_id
        session["registration_challenge_channel"] = channel
        masked_target = (
            target[:2] + "***" + target[target.find("@"):] if channel == "email" and "@" in target
            else (target[:3] + "****" + target[-3:] if len(target) >= 7 else "***")
        )
        record_operation(
            actor_type="anonymous", actor_id=None, actor_name=normalized.username, target_user=target_hint,
            action_category="account", action_code="user.register.verification_sent",
            action_name="用户注册验证码已发送", success=True, status_code=202,
            request_data={**safe_input, "verification_channel": channel},
        )
        return _page("验证联系方式", f"""
            <h2>输入验证码</h2>
            <p>验证码已发送到：{escape(masked_target)}</p>
            <form method="post" action="/user/register/verify">
                <p>验证码：<input name="code" inputmode="numeric" maxlength="8" required autocomplete="one-time-code"></p>
                <button type="submit">完成注册</button>
            </form>
            <p><a href="/user/register">重新注册或重新发送</a></p>
        """), 202
    except Exception as e:
        record_operation(
            actor_type="user", actor_id=None, actor_name=str(username).strip(), target_user=target_hint,
            action_category="account", action_code="user.register", action_name="用户注册",
            success=False, status_code=400 if isinstance(e, ValueError) else 503,
            error_code="registration_failed", error_message=str(e), request_data=safe_input,
        )
        status = 400 if isinstance(e, ValueError) else 503
        return _page("注册失败", f"<h2 class='error'>注册失败：{escape(str(e))}</h2><p><a href='/user/register'>返回注册</a></p>"), status


@user_bp.post("/register/verify")
def user_register_verify():
    if not _registration_attempt_allowed():
        return _page("注册受限", "<h2 class='error'>注册请求过于频繁，请稍后再试</h2>"), 429
    challenge_id = str(session.get("registration_challenge_id") or "")
    if not challenge_id:
        return _page("验证失败", "<h2 class='error'>注册验证会话已失效，请重新注册</h2><p><a href='/user/register'>重新注册</a></p>"), 400
    try:
        payload = verify_and_consume_challenge(challenge_id, request.form.get("code", ""))
        user, token = register_verified_user(
            username=payload.get("username"),
            password_hash=payload.get("password_hash"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            verified_channel=payload.get("_verified_channel"),
            verified_target=payload.get("_verified_target"),
        )
        session.pop("registration_challenge_id", None)
        session.pop("registration_challenge_channel", None)
        _establish_user_session(user)
        _sync_user_to_feishu_safely(int(user["id"]), reason="user_register_verified")
    except Exception as e:
        record_operation(
            actor_type="anonymous", actor_id=None, actor_name="", target_user=None,
            action_category="account", action_code="user.register.verification_failed",
            action_name="用户注册联系方式验证失败", success=False, status_code=400,
            error_code="registration_verification_failed", error_message=str(e), request_data={},
        )
        return _page("验证失败", f"<h2 class='error'>验证失败：{escape(str(e))}</h2><p><a href='/user/register'>重新注册</a></p>"), 400

    _, audit_ok = record_operation(
        actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
        target_user=user, action_category="account", action_code="user.register",
        action_name="用户注册", success=True, status_code=200,
        before_data={}, after_data={
            "registered": True,
            "register_source": user.get("register_source") or "self",
            "verified_channel": payload.get("_verified_channel"),
        }, request_data={"username": user.get("username"), "phone": user.get("phone"), "email": user.get("email")},
    )
    audit_warning = "" if audit_ok else "<p class='error'>注册成功，但审计系统异常，请管理员检查服务器日志。</p>"
    return _page("注册成功", f"""
        <h2 class="ok">注册成功</h2>{audit_warning}
        <p>用户ID：{user['id']}</p>
        <p>用户名：{escape(str(user.get('username') or ''))}</p>
        <p>你的 X-API-Token：</p>
        <textarea rows="3" readonly>{escape(token)}</textarea>
        <p class="muted">完整 Token 只显示本次，请立即安全保存。</p>
        <p><a href="/user/dashboard">进入用户中心</a></p>
    """)


@user_bp.route("/login", methods=["GET", "POST"])
def user_login():
    if request.method == "GET":
        return _page("用户登录", """
        <h2>用户登录</h2>
        <form method="post">
            <p>账号：<input name="account" required placeholder="用户名 / 手机号 / 邮箱"></p>
            <p>密码：<input name="password" type="password" required></p>
            <button type="submit">登录</button>
        </form>
        <p><a href="/user/register">注册账号</a> | <a href="/user/forgot-password">忘记密码？</a></p>
        """)

    account = request.form.get("account", "")
    password = request.form.get("password", "")
    try:
        account, password = validate_login_input(account, password)
    except ValueError:
        return _page(
            "登录失败",
            "<h2 class='error'>登录请求无效</h2><p><a href='/user/login'>重新登录</a></p>",
        ), 400
    login_key = f"{client_ip()}|{str(account).strip().lower()}"
    if _user_login_limiter.is_blocked(login_key):
        target_user = get_user_by_account(account) or {"username": str(account).strip()}
        record_operation(
            actor_type="anonymous",
            actor_id=None,
            actor_name=str(account).strip(),
            target_user=target_user,
            action_category="authentication",
            action_code="user.auth.login_rate_limited",
            action_name="用户登录被频率限制",
            success=False,
            status_code=429,
            error_code="login_rate_limited",
            error_message="登录失败次数过多",
            request_data={"account_supplied": bool(str(account).strip())},
        )
        return _page("登录受限", "<h2 class='error'>登录失败次数过多，请稍后再试</h2>"), 429
    user = authenticate_user(account, password)
    if not user:
        _user_login_limiter.record_failure(login_key)
        target_user = get_user_by_account(account) or {"username": str(account).strip()}
        error_code = (
            "account_disabled"
            if target_user.get("id") is not None
            and str(target_user.get("status") or "") != "active"
            else "invalid_credentials"
        )
        record_operation(
            actor_type="anonymous",
            actor_id=None,
            actor_name=str(account).strip(),
            target_user=target_user,
            action_category="authentication",
            action_code="user.auth.login_failed",
            action_name="用户登录失败",
            success=False,
            status_code=401,
            error_code=error_code,
            error_message="账号或密码错误",
            request_data={"account_supplied": bool(str(account).strip())},
        )
        return _page("登录失败", "<h2 class='error'>账号或密码错误</h2><p><a href='/user/login'>重新登录</a></p>"), 401
    _user_login_limiter.clear(login_key)
    _establish_user_session(user)
    record_operation(
        actor_type="user",
        actor_id=int(user["id"]),
        actor_name=str(user.get("username") or account),
        target_user=user,
        action_category="authentication",
        action_code="user.auth.login_success",
        action_name="用户登录成功",
        success=True,
        status_code=200,
        request_data={"account_supplied": bool(str(account).strip())},
    )
    return redirect("/user/dashboard")


@user_bp.route("/logout", methods=["POST"])
def user_logout():
    user_id = session.get("user_id")
    user = get_user_by_id(int(user_id)) if user_id else None
    if user_id:
        record_operation(
            actor_type="user",
            actor_id=int(user_id),
            actor_name=str((user or {}).get("username") or ""),
            target_user=user or {"id": int(user_id)},
            action_category="authentication",
            action_code="user.auth.logout",
            action_name="用户退出登录",
            success=True,
            status_code=200,
            request_data={"session_cleared": True},
        )
    session.clear()
    return redirect("/user/login")


@user_bp.route("/change-password", methods=["GET", "POST"])
def user_change_password():
    user = _current_user()
    if not user:
        return redirect("/user/login")
    if request.method == "GET":
        return _page("修改密码", """
        <h2>修改密码</h2>
        <form method="post">
            <p>当前密码：<input name="current_password" type="password" required></p>
            <p>新密码：<input name="new_password" type="password" required placeholder="至少{config.USER_PASSWORD_MIN_LENGTH}位"></p>
            <p>确认新密码：<input name="new_password2" type="password" required></p>
            <button type="submit">确认修改</button>
        </form>
        <p><a href="/user/dashboard">返回用户中心</a></p>
        """)

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    new_password2 = request.form.get("new_password2", "")
    if new_password != new_password2:
        record_operation(
            actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
            target_user=user, action_category="account", action_code="user.password_change",
            action_name="用户修改密码", success=False, status_code=400,
            error_code="password_confirmation_mismatch", error_message="两次新密码不一致",
            request_data={"password_changed": False},
        )
        return _page("修改失败", "<h2 class='error'>两次新密码不一致</h2><p><a href='/user/change-password'>返回</a></p>"), 400
    try:
        updated = change_user_password(int(user["id"]), current_password, new_password)
    except Exception as e:
        record_operation(
            actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
            target_user=user, action_category="account", action_code="user.password_change",
            action_name="用户修改密码", success=False, status_code=400,
            error_code="password_change_failed", error_message=str(e),
            request_data={"password_changed": False},
        )
        return _page("修改失败", f"<h2 class='error'>修改失败：{escape(str(e))}</h2><p><a href='/user/change-password'>返回</a></p>"), 400
    session["user_id"] = int(updated["id"])
    session["user_session_version"] = int(updated.get("session_version") or 1)
    session["user_csrf_token"] = secrets.token_urlsafe(32)
    _, audit_ok = record_operation(
        actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
        target_user=updated, action_category="account", action_code="user.password_change",
        action_name="用户修改密码", success=True, status_code=200,
        before_data={"password_changed": False}, after_data={"password_changed": True},
        request_data={"password_changed": True},
    )
    warning = "" if audit_ok else "<p class='error'>密码已修改，但审计系统异常，请联系管理员。</p>"
    return _page("修改成功", f"<h2 class='ok'>密码修改成功</h2>{warning}<p><a href='/user/dashboard'>返回用户中心</a></p>")


@user_bp.route("/dashboard", methods=["GET"])
def user_dashboard():
    user = _current_user()
    if not user:
        return redirect("/user/login")

    token = get_active_api_key(int(user["id"])) or get_or_create_api_key(int(user["id"]))
    sub = get_active_subscription(int(user["id"]))
    plan = get_plan_by_code(sub["plan_code"]) if sub else None
    scheduled_subs = get_scheduled_subscriptions(int(user["id"]))
    history_rows = list_membership_actions(int(user["id"]), limit=10)
    base_url = request.host_url.rstrip("/")

    scheduled_html = ""
    if scheduled_subs:
        scheduled_rows = "".join(
            f"<tr><td>{escape(str(item.get('plan_code') or ''))}</td>"
            f"<td>{escape(str(item.get('start_time') or ''))}</td>"
            f"<td>{escape(str(item.get('expire_time') or ''))}</td></tr>"
            for item in scheduled_subs
        )
        scheduled_html = f"""
        <h3>待生效套餐</h3>
        <table><tr><th>套餐</th><th>生效时间</th><th>到期时间</th></tr>{scheduled_rows}</table>
        """

    history_html = ""
    if history_rows:
        labels = {
            "open": "首次开通",
            "renew": "续费",
            "switch_now": "立即换套餐",
            "switch_scheduled": "到期后换套餐",
        }
        history_table_rows = "".join(
            f"<tr><td>{escape(labels.get(str(item.get('operation_type') or ''), str(item.get('operation_type') or '')))}</td>"
            f"<td>{escape(str(item.get('previous_plan_code') or '无'))}</td>"
            f"<td>{escape(str(item.get('plan_code') or ''))}</td>"
            f"<td>{escape(str(item.get('effective_time') or ''))}</td></tr>"
            for item in history_rows
        )
        history_html = f"""
        <h3>最近套餐记录</h3>
        <table><tr><th>操作</th><th>原套餐</th><th>目标套餐</th><th>生效时间</th></tr>{history_table_rows}</table>
        """

    if sub and plan:
        plan_html = f"""
        <h3 class="ok">接口套餐已开通</h3>
        <table>
            <tr><th>套餐</th><td>{escape(plan.get('plan_name') or '')} ({escape(sub.get('plan_code') or '')})</td></tr>
            <tr><th>类型</th><td>{escape(sub.get('plan_type') or '')}</td></tr>
            <tr><th>开始时间</th><td>{escape(sub.get('start_time') or '')}</td></tr>
            <tr><th>到期时间</th><td>{escape(sub.get('expire_time') or '')}</td></tr>
        </table>
        {scheduled_html}
        {history_html}
        """
    else:
        plan_html = f"""
        <h3 class="error">暂未开通接口套餐</h3>
        <p>当前账号是普通注册用户，已经可以登录用户中心，但还不能调用股票数据接口。</p>
        {_contact_html()}
        {scheduled_html}
        {history_html}
        """

    return _page("用户中心", f"""
    <h2>用户中心</h2>
    <p><a href="/user/change-password">修改密码</a></p><form method="post" action="/user/logout"><button type="submit">退出登录</button></form>
    <table>
        <tr><th>用户ID</th><td>{user['id']}</td></tr>
        <tr><th>用户名</th><td>{escape(str(user.get('username') or ''))}</td></tr>
        <tr><th>手机号</th><td>{escape(str(user.get('phone') or ''))}</td></tr>
        <tr><th>邮箱</th><td>{escape(str(user.get('email') or ''))}</td></tr>
        <tr><th>账号状态</th><td>{escape(str(user.get('status') or ''))}</td></tr>
        <tr><th>注册来源</th><td>{escape(str(user.get('register_source') or ''))}</td></tr>
    </table>
    <h3>X-API-Token</h3>
    <textarea rows="2" readonly>{escape(token)}</textarea>
    <p class="muted">出于安全原因，已有Token只显示前缀和后4位；完整Token仅在创建或轮换后显示一次。</p>
    <form method="post" action="/user/api-key/rotate" class="card">
        <h4>轮换API Token</h4>
        <p>当前密码：<input type="password" name="password" required autocomplete="current-password"></p>
        <button type="submit" data-confirm="旧Token将立即失效，确定轮换吗？">生成新Token</button>
    </form>
    {plan_html}
    {_api_integration_html("你的X-API-Token", base_url)}
    """)


@user_bp.post("/api-key/rotate")
def user_rotate_api_key():
    user = _current_user()
    if not user:
        return redirect("/user/login")
    password = request.form.get("password", "")
    if not verify_password(password, user.get("password_hash")):
        record_operation(
            actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
            target_user=user, action_category="security", action_code="user.api_key.rotate_failed",
            action_name="用户轮换API Token失败", success=False, status_code=403,
            error_code="invalid_password", error_message="当前密码错误", request_data={},
        )
        return _page("轮换失败", "<h2 class='error'>当前密码错误</h2><p><a href='/user/dashboard'>返回</a></p>"), 403
    new_token = rotate_api_key(int(user["id"]))
    record_operation(
        actor_type="user", actor_id=int(user["id"]), actor_name=str(user.get("username") or ""),
        target_user=user, action_category="security", action_code="user.api_key.rotate",
        action_name="用户轮换API Token", success=True, status_code=200,
        before_data={"rotated": False}, after_data={"rotated": True}, request_data={},
    )
    return _page("Token轮换成功", f"""
        <h2 class="ok">新Token已生成</h2>
        <p class="error">请立即复制保存。关闭本页后系统不会再次显示完整Token，旧Token已经失效。</p>
        <textarea rows="3" readonly>{escape(new_token)}</textarea>
        <p><a href="/user/dashboard">返回用户中心</a></p>
    """)


@user_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Create a reviewable password-reset request without disclosing account existence."""
    if request.method == "GET":
        return _page("找回密码", f"""
        <h2>找回密码</h2>
        <p class="muted">请输入账号和可联系到你的方式。管理员核实身份后会在后台重置密码。</p>
        <form method="post">
            <p>账号：<input name="account" required placeholder="用户名 / 手机号 / 邮箱"></p>
            <p>联系方式：<input name="contact" required placeholder="手机号 / 邮箱 / 微信 / QQ"></p>
            <button type="submit">提交找回申请</button>
        </form>
        <p class="muted">为保护账号安全，页面不会显示账号是否存在，也不会直接修改密码。</p>
        {_contact_html()}
        """)

    account = request.form.get("account", "").strip()
    contact = request.form.get("contact", "").strip()
    reset_key = f"{client_ip()}|{account.lower()}"
    if not account or not contact:
        return _page(
            "提交失败",
            "<h2 class='error'>请填写账号和联系方式</h2><p><a href='/user/forgot-password'>返回重新填写</a></p>",
        ), 400
    if _password_reset_limiter.is_blocked(reset_key):
        record_operation(
            actor_type="anonymous", actor_id=None, actor_name=account,
            target_user={"username": account}, action_category="authentication",
            action_code="user.password_reset_rate_limited", action_name="找回密码申请被频率限制",
            success=False, status_code=429, error_code="password_reset_rate_limited",
            error_message="找回密码申请过于频繁",
            request_data={"account_supplied": True, "contact_supplied": True},
        )
        return _page(
            "提交受限",
            "<h2 class='error'>提交过于频繁，请稍后再试</h2>",
        ), 429

    try:
        submit_password_reset_request(account=account, contact=contact)
        _password_reset_limiter.record_failure(reset_key)
    except Exception:
        logging.exception("[用户] 找回密码申请写入失败")
        record_operation(
            actor_type="anonymous", actor_id=None, actor_name=account,
            target_user={"username": account}, action_category="authentication",
            action_code="user.password_reset_request", action_name="提交找回密码申请",
            success=False, status_code=503, error_code="password_reset_request_failed",
            error_message="找回密码申请暂时不可用",
            request_data={"account_supplied": True, "contact_supplied": True},
        )
        return _page(
            "暂时不可用",
            f"<h2 class='error'>申请暂时无法提交，请稍后重试或联系管理员。</h2>{_contact_html()}",
        ), 503

    record_operation(
        actor_type="anonymous", actor_id=None, actor_name=account,
        target_user={"username": account}, action_category="authentication",
        action_code="user.password_reset_request", action_name="提交找回密码申请",
        success=True, status_code=202,
        request_data={"account_supplied": True, "contact_supplied": True},
    )
    return _page("申请已接收", f"""
    <h2 class="ok">申请已接收</h2>
    <p>如果信息可以匹配到账号，管理员会在核实身份后处理。</p>
    <p>为保护隐私，本页面不会确认账号是否存在。</p>
    {_contact_html()}
    <p><a href="/user/login">返回登录</a></p>
    """), 202


# =========================
# 平台 API 接口文档（动态版）
# =========================
def _render_param_table(params_text: str) -> str:
    """把后台填的参数文本渲染成表格。

    格式：每行一个参数，使用 | 分隔：
    参数名|类型|是否必填|示例|说明
    """
    text = (params_text or "").strip()
    if not text:
        return "<p class='muted'>无请求参数。</p>"
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        while len(parts) < 5:
            parts.append("")
        name, typ, required, example, desc = parts[:5]
        rows.append(f"""
        <tr>
            <td><code>{escape(name)}</code></td>
            <td>{escape(typ)}</td>
            <td>{escape(required)}</td>
            <td><code>{escape(example)}</code></td>
            <td>{escape(desc)}</td>
        </tr>
        """)
    if not rows:
        return "<p class='muted'>无请求参数。</p>"
    return f"""
    <table class="endpoint-table">
        <tr><th>参数名</th><th>类型</th><th>是否必填</th><th>示例</th><th>说明</th></tr>
        {''.join(rows)}
    </table>
    """


def _make_default_examples(method: str, full_url: str, token: str) -> tuple[str, str, str]:
    method = (method or "GET").upper()
    token = token or "你的X-API-Token"
    if method == "GET":
        curl_code = f'''curl -X GET "{full_url}" ^
  -H "X-API-Token: {token}"'''
        python_code = f'''import requests

url = "{full_url}"
headers = {{"X-API-Token": "{token}"}}
resp = requests.get(url, headers=headers, timeout=20)
print(resp.status_code)
print(resp.json())'''
        js_code = f'''fetch("{full_url}", {{
  method: "GET",
  headers: {{"X-API-Token": "{token}"}}
}})
  .then(res => res.json())
  .then(data => console.log(data));'''
    else:
        curl_code = f'''curl -X {method} "{full_url}" ^
  -H "X-API-Token: {token}" ^
  -H "Content-Type: application/json" ^
  -d "{{}}"'''
        python_code = f'''import requests

url = "{full_url}"
headers = {{"X-API-Token": "{token}"}}
resp = requests.{method.lower()}(url, json={{}}, headers=headers, timeout=20)
print(resp.status_code)
print(resp.json())'''
        js_code = f'''fetch("{full_url}", {{
  method: "{method}",
  headers: {{
    "X-API-Token": "{token}",
    "Content-Type": "application/json"
  }},
  body: JSON.stringify({{}})
}})
  .then(res => res.json())
  .then(data => console.log(data));'''
    return curl_code, python_code, js_code


def _linkify_doc_text(value: str) -> str:
    """Escape document text and turn plain HTTP(S) URLs into safe links."""
    escaped = escape(value or "")
    url_re = re.compile(r"(https?://[^\s<]+)")
    linked = url_re.sub(
        lambda match: f'<a href="{match.group(1)}" target="_blank" rel="noopener noreferrer">{match.group(1)}</a>',
        escaped,
    )
    return linked.replace("\n", "<br>")


def _doc_permission_kind(scope: str) -> tuple[str, str]:
    scope = (scope or "").strip()
    if scope == "tushare:points15000:read":
        return "general", "通用接口"
    if scope.startswith("tushare:independent:"):
        return "special", "特殊权限·Tushare单独权限"
    if scope == "market:kaipanla:read":
        return "special", "特殊权限·开盘啦"
    return "other", "其他权限"


def _strip_static_test_status(description: str) -> str:
    """Hide generated catalog test labels; runtime reports are authoritative."""
    lines = []
    for line in str(description or "").splitlines():
        if line.strip().startswith("最新实测状态："):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _doc_runtime_status(endpoint: dict) -> dict:
    status = endpoint.get("runtime_status")
    if isinstance(status, dict) and status.get("status_key"):
        return status
    return {
        "status_key": "unverified",
        "status_label": "暂无有效实测记录",
        "http_status": None,
        "data_count": 0,
        "verdict": "尚未被最近一次有效全接口报告覆盖",
        "problem_category": "",
        "fallback_used": False,
        "data_freshness": "",
        "actual_trade_date": None,
    }


def _doc_status_class(status_key: str) -> str:
    if status_key == "healthy":
        return "status-ok"
    if status_key == "fallback":
        return "status-fallback"
    if status_key == "callable_empty":
        return "status-empty"
    if status_key == "unverified":
        return "status-unverified"
    return "status-warn"


@user_bp.get("/api-docs/status.json")
def api_docs_status():
    statistics = get_api_doc_statistics(public_only=True)
    category_count = int(statistics.get("category_count") or 0)
    document_count = int(statistics.get("document_count") or 0)
    general_count = int(statistics.get("general_count") or 0)
    special_count = int(statistics.get("special_count") or 0)
    ui_revision = (
        f"public:{category_count}:{document_count}:{general_count}:{special_count}"
    )
    response = jsonify({
        "success": True,
        "ui_revision": ui_revision,
        "category_count": category_count,
        "document_count": document_count,
        "general_count": general_count,
        "special_count": special_count,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@user_bp.route("/api-docs", methods=["GET"])
def api_docs():
    """User-facing complete platform API documentation."""
    user = _current_user()
    token = "你的X-API-Token"
    if user:
        token = "你的X-API-Token（完整值仅在创建或轮换时显示）"

    docs = list_public_docs()
    statistics = get_api_doc_statistics(public_only=True)
    base_url = request.host_url.rstrip("/")
    category_count = int(statistics.get("category_count") or 0)
    document_count = int(statistics.get("document_count") or 0)
    general_count = int(statistics.get("general_count") or 0)
    special_count = int(statistics.get("special_count") or 0)
    ui_revision = escape(
        f"public:{category_count}:{document_count}:{general_count}:{special_count}",
        quote=True,
    )

    if not docs:
        admin_api_docs_url = escape(admin_url("/admin/api-docs"), quote=True)
        return _page("平台API接口", f"""
        <h2>平台API接口文档</h2>
        <p class="muted">暂无已发布的接口文档。请管理员到 <a href="{admin_api_docs_url}">API文档管理</a> 添加。</p>
        """)

    nav_category_parts = []
    content_parts = []
    total_count = document_count
    other_scope_count = max(total_count - general_count - special_count, 0)

    for cat in docs:
        cat_id = f"cat-{cat['id']}"
        endpoint_nav = []
        endpoint_count = len(cat.get("endpoints", []))
        content_parts.append(f"""
        <section id="{cat_id}" class="doc-category-header">
            <h2>{escape(cat.get('name') or '未命名类目')} <span class="category-count">{endpoint_count}</span></h2>
            <p class="muted">{escape(cat.get('description') or '')}</p>
        </section>
        """)

        for ep in cat.get("endpoints", []):
            ep_id = f"ep-{ep['id']}"
            title = ep.get("title") or "未命名接口"
            method = (ep.get("method") or "GET").upper()
            path = ep.get("path") or ""
            full_url = base_url + path if path.startswith("/") else base_url + "/" + path
            curl_code, python_code, js_code = _make_default_examples(method, full_url, token)

            request_example = (ep.get("request_example") or "").strip()
            response_example = (ep.get("response_example") or "").strip()
            error_codes = (ep.get("error_codes") or "").strip()
            headers_text = (ep.get("headers_text") or "").strip() or f"X-API-Token: {token}"
            headers_text = headers_text.replace("用户自己的Token", token).replace("你的X-API-Token", token)

            raw_description = ep.get("description") or ""
            description = _strip_static_test_status(raw_description)
            status_record = ep.get("runtime_status")
            raw_status_key = (
                str(status_record.get("status_key") or "unverified")
                if isinstance(status_record, dict)
                else "unverified"
            )
            public_status_key = (
                "available"
                if raw_status_key in {"healthy", "fallback", "callable_empty"}
                else "unverified"
                if raw_status_key == "unverified"
                else "unavailable"
            )
            public_status_text = {
                "available": "可调用",
                "unavailable": "暂不可用",
                "unverified": "暂无有效实测记录",
            }[public_status_key]
            permission_kind, permission_label = _doc_permission_kind(ep.get("scope") or "")
            _, api_name = endpoint_identity_from_path(path)
            if not api_name:
                api_name = path.split("?", 1)[0].rstrip("/").split("/")[-1]
            search_text = " ".join([
                str(title),
                str(api_name),
                str(cat.get("name") or ""),
                str(path),
                str(description),
                permission_label,
                public_status_text,
                public_status_key,
            ]).lower()

            endpoint_nav.append(
                f'<li class="doc-nav-endpoint" data-permission="{permission_kind}" '
                f'data-health="{escape(public_status_key, quote=True)}" '
                f'data-availability="{escape(public_status_key, quote=True)}" '
                f'data-search="{escape(search_text, quote=True)}">'
                f'<a href="#{ep_id}"><code>{escape(api_name)}</code> {escape(title)}</a></li>'
            )

            default_response = '{\n  "success": true,\n  "code": 200,\n  "count": 0,\n  "data": [],\n  "msg": "获取成功，共0条"\n}'
            default_errors = '401 Token缺失或无效\n402 套餐未开通或已过期\n403 当前套餐无权限\n429 调用额度或频率受限\n502 上游数据源调用失败\n500 服务异常'

            request_example_html = ""
            if request_example:
                request_example_html = f"<h4>请求示例</h4><pre><code>{escape(request_example)}</code></pre>"

            status_class = (
                "status-ok"
                if public_status_key == "available"
                else "status-unverified"
                if public_status_key == "unverified"
                else "status-warn"
            )
            permission_class = "permission-general" if permission_kind == "general" else "permission-special"

            content_parts.append(f"""
            <section id="{ep_id}" class="doc-section endpoint-card"
                     data-permission="{permission_kind}"
                     data-health="{escape(public_status_key, quote=True)}"
                     data-availability="{escape(public_status_key, quote=True)}"
                     data-search="{escape(search_text, quote=True)}">
                <div class="endpoint-title-row">
                    <div>
                        <h3><code>{escape(api_name)}</code> · {escape(title)}</h3>
                        <div class="badges">
                            <span class="badge {permission_class}">{escape(permission_label)}</span>
                            <span class="badge {status_class}">状态：{escape(public_status_text)}</span>
                            <span class="badge badge-method">{escape(method)}</span>
                        </div>
                    </div>
                    <a class="back-top" href="#api-doc-top">返回顶部</a>
                </div>
                <p class="doc-description">{_linkify_doc_text(description)}</p>
                <table class="endpoint-table">
                    <tr><th>请求方式</th><td><b>{escape(method)}</b></td></tr>
                    <tr><th>接口地址</th><td><code>{escape(path)}</code></td></tr>
                    <tr><th>完整地址</th><td><code>{escape(full_url)}</code></td></tr>
                    <tr><th>权限 Scope</th><td><code>{escape(ep.get('scope') or '无特殊Scope')}</code></td></tr>
                    <tr><th>请求头</th><td><pre><code>{escape(headers_text)}</code></pre></td></tr>
                </table>

                <h4>请求参数（最新验收示例）</h4>
                {_render_param_table(ep.get('params_text') or '')}

                {request_example_html}

                <details class="code-details">
                    <summary>调用代码：curl</summary>
                    <pre><code>{escape(curl_code)}</code></pre>
                </details>

                <details class="code-details">
                    <summary>调用代码：Python requests</summary>
                    <pre><code>{escape(python_code)}</code></pre>
                </details>

                <details class="code-details">
                    <summary>调用代码：JavaScript fetch</summary>
                    <pre><code>{escape(js_code)}</code></pre>
                </details>

                <details class="code-details">
                    <summary>返回示例</summary>
                    <pre><code>{escape(response_example or default_response)}</code></pre>
                </details>

                <details class="code-details">
                    <summary>错误码说明</summary>
                    <pre><code>{escape(error_codes or default_errors)}</code></pre>
                </details>
            </section>
            """)

        nav_category_parts.append(f"""
        <details class="nav-category" open>
            <summary><a href="#{cat_id}">{escape(cat.get('name') or '未命名类目')}</a> <span>{endpoint_count}</span></summary>
            <ul>{''.join(endpoint_nav)}</ul>
        </details>
        """)

    other_scope_kpi = (
        f"<span><b>{other_scope_count}</b> 其他权限</span>" if other_scope_count else ""
    )

    html = f"""
    <div id="api-doc-top" class="api-doc-page">
        <div class="api-doc-toolbar">
            <div>
                <h1>平台API接口文档</h1>
                <p class="muted">完整收录{total_count}个接口文档。公开页面仅展示接口目录、权限和粗粒度可用性，不公开内部运行时遥测。</p>
            </div>
            <div class="doc-kpis">
                <span><b>{total_count}</b> 全部接口</span>
                <span><b>{general_count}</b> 通用接口</span>
                <span><b>{special_count}</b> 特殊权限</span>
                {other_scope_kpi}
            </div>
        </div>

        <div class="api-doc-controls">
            <input id="apiDocSearch" type="search" placeholder="搜索接口英文名、中文名、分类、路径……" autocomplete="off">
            <button type="button" class="filter-btn active" data-filter="all">全部</button>
            <button type="button" class="filter-btn" data-filter="general">通用接口</button>
            <button type="button" class="filter-btn" data-filter="special">特殊权限</button>
            <button type="button" class="filter-btn" data-filter="available">可调用</button>
            <button type="button" class="filter-btn" data-filter="unavailable">暂不可用</button>
            <button type="button" class="filter-btn" data-filter="unverified">暂无实测</button>
            <span id="apiDocVisibleCount" class="muted">当前显示 {total_count} 个接口</span>
        </div>

        <div class="api-doc-layout">
            <aside class="api-doc-sidebar">
                <h3>接口目录</h3>
                <div id="apiDocNav">{''.join(nav_category_parts)}</div>
            </aside>
            <main class="api-doc-main">
                {''.join(content_parts)}
                <div id="apiDocEmpty" class="doc-empty" hidden>没有找到符合条件的接口。</div>
            </main>
        </div>
    </div>
    <link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-user-routes-l1271-8ca4484eec.css">
    <script>
    (() => {{
        const search = document.getElementById('apiDocSearch');
        const buttons = Array.from(document.querySelectorAll('.filter-btn'));
        const cards = Array.from(document.querySelectorAll('.endpoint-card'));
        const navItems = Array.from(document.querySelectorAll('.doc-nav-endpoint'));
        const categories = Array.from(document.querySelectorAll('.nav-category'));
        const countLabel = document.getElementById('apiDocVisibleCount');
        const empty = document.getElementById('apiDocEmpty');
        let activeFilter = 'all';

        function matches(el, query) {{
            const permission = el.dataset.permission || '';
            const health = el.dataset.health || '';
            const text = (el.dataset.search || '').toLowerCase();
            const filterOk = (
                activeFilter === 'all' ||
                permission === activeFilter ||
                health === activeFilter
            );
            return filterOk && (!query || text.includes(query));
        }}

        function applyFilter() {{
            const query = (search.value || '').trim().toLowerCase();
            let visible = 0;
            cards.forEach(card => {{
                const show = matches(card, query);
                card.hidden = !show;
                if (show) visible += 1;
            }});
            navItems.forEach(item => {{ item.hidden = !matches(item, query); }});
            categories.forEach(category => {{
                const hasVisible = Array.from(category.querySelectorAll('.doc-nav-endpoint')).some(item => !item.hidden);
                category.hidden = !hasVisible;
            }});
            document.querySelectorAll('.doc-category-header').forEach(header => {{
                let next = header.nextElementSibling;
                let hasVisible = false;
                while (next && !next.classList.contains('doc-category-header')) {{
                    if (next.classList.contains('endpoint-card') && !next.hidden) hasVisible = true;
                    next = next.nextElementSibling;
                }}
                header.hidden = !hasVisible;
            }});
            countLabel.textContent = `当前显示 ${{visible}} 个接口`;
            empty.hidden = visible !== 0;
        }}

        buttons.forEach(button => {{
            button.addEventListener('click', () => {{
                buttons.forEach(item => item.classList.remove('active'));
                button.classList.add('active');
                activeFilter = button.dataset.filter || 'all';
                applyFilter();
            }});
        }});
        search.addEventListener('input', applyFilter);

        let currentRevision = '{ui_revision}';
        const pollIntervalMs = 60000;
        async function pollApiDocRevision() {{
            try {{
                const response = await fetch('/user/api-docs/status.json', {{cache: 'no-store'}});
                if (!response.ok) return;
                const payload = await response.json();
                const nextRevision = String(payload.ui_revision || '');
                if (currentRevision && nextRevision && nextRevision !== currentRevision) {{
                    sessionStorage.setItem('userApiDocsScrollY', String(window.scrollY || 0));
                    window.location.reload();
                    return;
                }}
                currentRevision = nextRevision || currentRevision;
            }} catch (error) {{
                console.warn('API文档状态检查失败', error);
            }}
        }}
        const savedScrollY = Number(sessionStorage.getItem('userApiDocsScrollY') || 0);
        if (savedScrollY > 0) {{
            sessionStorage.removeItem('userApiDocsScrollY');
            window.scrollTo(0, savedScrollY);
        }}
        window.setInterval(pollApiDocRevision, pollIntervalMs);
    }})();
    </script>
    """
    return _page("平台API接口文档", html)
