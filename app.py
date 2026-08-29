# -*- coding: utf-8 -*-
"""Stock data API server entry point."""
from __future__ import annotations

import atexit
import hmac
import logging
import queue
import re
import secrets
import sys
import time
from datetime import timedelta
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler

from flask import Flask, g, request, session
from flask_compress import Compress
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import config
from db_utils import assert_schema_ready, close_thread_connection, get_conn, init_db
from routes.admin_api_doc_routes import admin_api_doc_bp
from routes.admin_audit_routes import admin_audit_bp
from routes.admin_member_routes import admin_member_bp
from routes.admin_market_test_routes import admin_market_test_bp
from routes.admin_user_routes import admin_user_bp
from routes.admin_sync_routes import admin_sync_bp
from routes.market_data_routes import market_data_bp
from routes.user_routes import user_bp
from services.market_data_service import (
    start_market_data_background_services,
    stop_market_data_background_services,
)
from services.usage_log_queue import start_usage_log_worker, stop_usage_log_worker
from services.audit_cleanup import start_audit_cleanup_worker, stop_audit_cleanup_worker
from services.audit_service import begin_api_audit, finish_api_audit, mark_api_auth_state
from services.audit_spool import start_audit_spool_worker, stop_audit_spool_worker
from services.environment_guard import assert_environment_ready
from services.production_readiness import assert_production_ready
from services.redis_backend import get_redis
from utils.common import make_resp

_log_listener: QueueListener | None = None


def setup_logging() -> QueueListener:
    """Configure one queue-backed rotating log writer for Windows-safe logging."""
    global _log_listener
    if _log_listener is not None:
        return _log_listener

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler = TimedRotatingFileHandler(
        filename=config.LOG_DIR / "stock_server.log",
        when="midnight",
        interval=1,
        backupCount=config.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    log_queue: queue.Queue = queue.Queue(-1)
    listener = QueueListener(log_queue, file_handler, console_handler, respect_handler_level=True)
    listener.start()

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(QueueHandler(log_queue))

    _log_listener = listener
    logging.info("日志系统初始化完成: %s", config.LOG_DIR / "stock_server.log")
    return listener


def stop_background_services() -> None:
    try:
        stop_market_data_background_services()
    except Exception:
        logging.exception("停止行情缓存后台服务失败")
    try:
        stop_usage_log_worker()
    except Exception:
        logging.exception("停止 usage_logs 写入线程失败")
    try:
        stop_audit_cleanup_worker()
    except Exception:
        logging.exception("停止审计自动清理线程失败")
    try:
        stop_audit_spool_worker()
    except Exception:
        logging.exception("停止审计持久化线程失败")
    if (
        config.ENABLE_FEISHU_SYNC
        and config.ENABLE_IN_PROCESS_FEISHU_WORKER
        and "services.feishu_sync_service" in sys.modules
    ):
        try:
            from services.feishu_sync_service import stop_sync_service
            stop_sync_service()
        except Exception:
            logging.exception("停止飞书同步服务失败")
    try:
        from services.api_doc_status_scheduler import stop_api_doc_status_scheduler
        stop_api_doc_status_scheduler()
    except Exception:
        logging.exception("停止API文档状态刷新服务失败")
    try:
        from services.tushare_spec_monitor_scheduler import stop_tushare_spec_monitor_scheduler
        stop_tushare_spec_monitor_scheduler()
    except Exception:
        logging.exception("停止Tushare官网规格监控失败")
    try:
        from services.admin_api_test_batch_service import stop_admin_api_test_worker
        from services.admin_api_test_cleanup_service import stop_admin_api_test_cleanup_worker
        stop_admin_api_test_worker()
        stop_admin_api_test_cleanup_worker()
    except Exception:
        logging.exception("停止管理员接口测试后台服务失败")
    global _log_listener
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None
    global _runtime_started, _web_services_started
    _runtime_started = False
    _web_services_started = False
_web_services_started = False
_runtime_started = False
_runtime_lock = __import__("threading").Lock()


def start_web_process_services() -> bool:
    """Start queues/caches that belong to each WSGI worker process."""
    global _web_services_started
    with _runtime_lock:
        if _web_services_started:
            return False
        start_usage_log_worker()
        try:
            start_audit_spool_worker()
        except Exception:
            logging.exception("审计持久化线程启动失败")
        try:
            start_market_data_background_services()
        except Exception:
            logging.exception("行情缓存后台服务启动失败")
        _web_services_started = True
        return True


def start_runtime_services() -> bool:
    """Start single-process schedulers for the development/Waitress mode."""
    global _runtime_started
    start_web_process_services()
    with _runtime_lock:
        if _runtime_started:
            return False
        try:
            start_audit_cleanup_worker()
        except Exception:
            logging.exception("审计自动清理线程启动失败")
        try:
            from services.api_doc_status_scheduler import start_api_doc_status_scheduler
            start_api_doc_status_scheduler()
        except Exception:
            logging.exception("API文档状态刷新服务启动失败")
        try:
            from services.tushare_spec_monitor_scheduler import start_tushare_spec_monitor_scheduler
            start_tushare_spec_monitor_scheduler()
        except Exception:
            logging.exception("Tushare官网规格监控启动失败")
        if config.ADMIN_API_TEST_IN_PROCESS_WORKER:
            try:
                from services.admin_api_test_batch_service import start_admin_api_test_worker
                from services.admin_api_test_cleanup_service import start_admin_api_test_cleanup_worker
                start_admin_api_test_worker()
                start_admin_api_test_cleanup_worker()
            except Exception:
                logging.exception("管理员接口测试后台服务启动失败")
        if config.ENABLE_FEISHU_SYNC and config.ENABLE_IN_PROCESS_FEISHU_WORKER:
            try:
                from services.feishu_sync_service import start_sync_service
                start_sync_service()
            except Exception:
                logging.exception("飞书同步服务启动失败")
        elif config.ENABLE_FEISHU_SYNC:
            logging.info("飞书后台同步由独立 worker 负责")
        _runtime_started = True
        return True


def create_app(*, start_background: bool = False, configure_logging: bool = False) -> Flask:
    if configure_logging:
        setup_logging()

    assert_environment_ready(config)
    if config.APP_ENV == "production":
        assert_production_ready(config, redis_getter=get_redis)
    if bool(getattr(config, "DB_AUTO_MIGRATE", config.APP_ENV != "production")):
        init_db()
    else:
        assert_schema_ready()

    app = Flask(__name__)
    if config.TRUST_PROXY_HEADERS:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=config.PROXY_FIX_X_FOR,
            x_proto=config.PROXY_FIX_X_PROTO,
            x_host=config.PROXY_FIX_X_HOST,
        )


    app.secret_key = config.SECRET_KEY
    app.config.update(
        MAX_CONTENT_LENGTH=config.MAX_REQUEST_BODY_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=config.SESSION_LIFETIME_MINUTES),
    )
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}}, supports_credentials=False)
    Compress(app)

    app.register_blueprint(admin_member_bp, url_prefix="/admin")
    app.register_blueprint(admin_user_bp, url_prefix="/admin")
    app.register_blueprint(admin_audit_bp, url_prefix="/admin")
    app.register_blueprint(admin_api_doc_bp, url_prefix="/admin")
    app.register_blueprint(admin_market_test_bp, url_prefix="/admin")
    app.register_blueprint(admin_sync_bp, url_prefix="/api/admin")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(market_data_bp, url_prefix="/api/v1/market")

    @app.before_request
    def request_started():
        g.request_started_at = time.monotonic()
        g.csp_nonce = secrets.token_urlsafe(18)
        begin_api_audit()
        if request.path.startswith("/admin") and config.ADMIN_IP_WHITELIST:
            from services.web_security import client_ip
            allowed = {str(value).strip() for value in config.ADMIN_IP_WHITELIST if str(value).strip()}
            if client_ip() not in allowed:
                return "当前 IP 不允许访问后台", 403
        if request.path.startswith("/admin"):
            from services.admin_auth import verify_admin_client_certificate_request
            cert_result = verify_admin_client_certificate_request()
            if not cert_result.ok:
                logging.warning(
                    "[管理员证书] 拒绝请求 path=%s code=%s ip=%s",
                    request.path, cert_result.code, request.remote_addr,
                )
                return (
                    "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
                    "<title>管理员客户端证书验证失败</title>"
                    "<link rel='stylesheet' href='/static/csp/r5-inline-attributes.css'><body class='csp-r5-6a41acc3b07d33fb'>"
                    "<h2>管理员客户端证书验证失败</h2>"
                    "<p>请使用已安装并登记的管理员客户端证书访问专用后台域名。</p>"
                    f"<p>错误代码：{cert_result.code}</p></body></html>",
                    403,
                )
            g.admin_client_certificate = cert_result.certificate
            if session.get("admin_logged_in") is True:
                from services.admin_auth import (
                    admin_client_certificate_required,
                    admin_session_certificate_matches,
                )
                if admin_client_certificate_required() and not admin_session_certificate_matches(
                    session.get("admin_certificate_fingerprint"),
                    cert_result.certificate,
                ):
                    logging.warning(
                        "[管理员证书] 会话证书发生变化 path=%s ip=%s",
                        request.path,
                        request.remote_addr,
                    )
                    session.clear()
                    return "管理员会话与客户端证书不匹配，请重新登录", 403
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = ""
            if request.path.startswith("/admin") and request.path != "/admin/login" and session.get("admin_logged_in") is True:
                expected = str(session.get("admin_csrf_token") or "")
            elif request.path.startswith("/user") and request.path not in {"/user/login", "/user/register", "/user/forgot-password"} and session.get("user_id"):
                expected = str(session.get("user_csrf_token") or "")
            if expected:
                supplied = str(request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or "")
                if not supplied or not hmac.compare_digest(expected, supplied):
                    return {"success": False, "code": 403, "data": [], "msg": "CSRF校验失败"}, 403
        if config.ENABLE_HTTP_ACCESS_LOG:
            logging.info(
                "[HTTP-IN] ip=%s method=%s path=%s ua=%s xff=%s",
                request.remote_addr,
                request.method,
                request.path,
                request.headers.get("User-Agent", ""),
                request.headers.get("X-Forwarded-For", ""),
            )

    @app.after_request
    def request_finished(response):
        finish_api_audit(response)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        nonce = str(getattr(g, "csp_nonce", "") or "")
        csp = (
            "default-src 'self'; object-src 'none'; img-src 'self' data:; "
            "connect-src 'self'; style-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; script-src-attr 'none'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.is_secure or config.APP_ENV == "production":
            csp += "; upgrade-insecure-requests"
        response.headers.setdefault("Content-Security-Policy", csp)
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith(("/admin", "/user")):
            response.headers.setdefault("Cache-Control", "no-store")
        content_type = str(response.headers.get("Content-Type") or "")
        if "text/html" in content_type and response.status_code < 400:
            csrf_token = ""
            if session.get("admin_logged_in") is True and request.path.startswith("/admin"):
                csrf_token = str(session.get("admin_csrf_token") or "")
                if not csrf_token:
                    csrf_token = secrets.token_urlsafe(32)
                    session["admin_csrf_token"] = csrf_token
            elif session.get("user_id") and request.path.startswith("/user"):
                csrf_token = str(session.get("user_csrf_token") or "")
                if not csrf_token:
                    csrf_token = secrets.token_urlsafe(32)
                    session["user_csrf_token"] = csrf_token
            html = response.get_data(as_text=True)
            if '/static/csp/r5-inline-attributes.css' not in html:
                style_helper = '<link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">'
                html = (
                    re.sub(
                        r'</head\s*>',
                        style_helper + '</head>',
                        html,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                    if re.search(r'</head\s*>', html, re.IGNORECASE)
                    else style_helper + html
                )
            if nonce:
                html = re.sub(
                    r"<script(?![^>]*\bnonce=)([^>]*)>",
                    lambda m: f'<script nonce="{nonce}"{m.group(1)}>',
                    html,
                    flags=re.IGNORECASE,
                )
            if csrf_token:
                hidden = f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
                html = re.sub(r'(<form\b[^>]*\bmethod=["\']?post["\']?[^>]*>)', lambda m: m.group(1) + hidden, html, flags=re.IGNORECASE)
            if '/static/js/security-ui.js' not in html:
                helper = '<script src="/static/js/security-ui.js" defer></script>'
                html = re.sub(r'</body\s*>', helper + '</body>', html, count=1, flags=re.IGNORECASE) if re.search(r'</body\s*>', html, re.IGNORECASE) else html + helper
            response.set_data(html)
        if config.ENABLE_HTTP_ACCESS_LOG:
            logging.info(
                "[HTTP-OUT] ip=%s method=%s path=%s status=%s cost=%.2fms",
                request.remote_addr,
                request.method,
                request.path,
                response.status_code,
                (time.monotonic() - getattr(g, "request_started_at", time.monotonic())) * 1000,
            )
        return response

    @app.teardown_request
    def request_teardown(exc):
        if exc is not None:
            finish_api_audit(None, exc)

    @app.teardown_appcontext
    def close_request_database_connection(exc):
        # The connection is thread-local. Closing it at the Flask context
        # boundary prevents any missed commit/rollback from leaking a lock
        # into the next request handled by the same Waitress worker thread.
        close_thread_connection()

    @app.get("/")
    def index():
        return {
            "success": True,
            "service": "股票数据API服务",
            "status": "正常运行",
            "docs": {
                "providers": "/api/v1/market/providers",
                "tushare": "/api/v1/market/tushare/catalog",
                "kaipanla": "/api/v1/market/kaipanla/catalog",
            },
            "auth_header": "X-API-Token",
        }

    @app.get("/ping")
    def ping():
        # Keep the liveness probe strictly plain text. Returning a bare string makes
        # Flask default to text/html, which would trigger the global HTML hardening
        # hook and append security-ui.js to the probe body.
        return app.response_class("pong", status=200, mimetype="text/plain")

    @app.get("/health/ready")
    def readiness():
        checks = {"database": False, "redis": False}
        try:
            get_conn().execute("SELECT 1").fetchone()
            checks["database"] = True
        except Exception:
            pass
        try:
            client = get_redis()
            checks["redis"] = bool(client is not None and client.ping())
        except Exception:
            pass
        required_redis = bool(getattr(config, "REDIS_REQUIRED", False))
        ready = checks["database"] and (checks["redis"] or not required_redis)
        return {"success": ready, "status": "ready" if ready else "not_ready", "checks": checks}, (200 if ready else 503)

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.errorhandler(Exception)
    def handle_exception(exc):
        if isinstance(exc, HTTPException):
            return make_resp(False, [], exc.description), exc.code
        mark_api_auth_state(
            "internal_error", error_code="internal_error", error_message=str(exc)
        )
        logging.error(
            "[全局异常] type=%s",
            type(exc).__name__,
        )
        return make_resp(False, [], "服务器内部异常，请联系管理员"), 500

    if start_background:
        start_runtime_services()

    return app


app = create_app(start_background=False, configure_logging=False)
atexit.register(stop_background_services)


if __name__ == "__main__":
    from waitress import serve

    setup_logging()
    start_runtime_services()
    logging.info("服务启动: http://%s:%s", config.SERVER_HOST, config.SERVER_PORT)
    serve(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        threads=config.SERVER_THREADS,
        connection_limit=config.WAITRESS_CONNECTION_LIMIT,
        channel_timeout=config.WAITRESS_CHANNEL_TIMEOUT,
    )
