# -*- coding: utf-8 -*-
"""One-click membership, subscription and scope test for stock_server.

Run from the project root:
    python -m tools.membership_tester

The script uses reserved test users only and does not require external packages.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import config
from config import DB_FILE
from db_utils import ensure_default_plans, get_conn, init_db
from services.environment_guard import collect_environment_errors
from services.member_service import create_or_get_user, get_or_create_api_key, open_subscription
from services.plan_catalog import scope_allowed

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOKEN_FILE = ROOT / "data-test" / "membership_test_tokens.json"


def resolve_base_url(value: str | None, *, allow_local_production_port: bool = False) -> str:
    configured = (value or os.getenv("STOCK_TEST_BASE_URL") or "").strip().rstrip("/")
    if not configured:
        raise ValueError("必须显式设置 STOCK_TEST_BASE_URL；禁止使用隐式生产端口默认值")
    parsed = urlsplit(configured)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"STOCK_TEST_BASE_URL 格式无效：{configured}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("STOCK_TEST_BASE_URL 只能填写协议、主机和端口，不能包含账号、路径、查询参数或片段")
    host = parsed.hostname.lower()
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    if allow_local_production_port:
        if not (loopback and port == 8899):
            raise ValueError("生产模拟确认仅允许访问本机回环地址 8899")
        return configured
    if port == 8899 or host in {
        "api.lifesupermarket.cn",
        "admin-api.lifesupermarket.cn",
        "lifesupermarket.cn",
        "www.lifesupermarket.cn",
    }:
        raise ValueError(f"拒绝对生产端口或生产域名执行破坏性会员测试：{configured}")
    is_local_test = loopback and port == 8898
    is_public_test = (
        host == "test-api.lifesupermarket.cn"
        and parsed.scheme.lower() == "https"
        and port == 443
    )
    if not (is_local_test or is_public_test):
        raise ValueError(
            "会员测试只允许测试实例 http://127.0.0.1:8898、"
            "http://localhost:8898 或 https://test-api.lifesupermarket.cn"
        )
    return configured


def resolve_token_file(value: str | Path | None) -> Path:
    configured = value or os.getenv("STOCK_TEST_TOKEN_FILE")
    if not configured:
        return DEFAULT_TOKEN_FILE
    path = Path(configured).expanduser()
    return path if path.is_absolute() else ROOT / path


BASE_URL = ""
TEST_MARKERS = {
    "general": "__MEMBERSHIP_TEST_GENERAL__",
    "special": "__MEMBERSHIP_TEST_SPECIAL__",
    "admin": "__MEMBERSHIP_TEST_ADMIN__",
    "expired": "__MEMBERSHIP_TEST_EXPIRED__",
    "disabled": "__MEMBERSHIP_TEST_DISABLED__",
    "unsubscribed": "__MEMBERSHIP_TEST_UNSUBSCRIBED__",
}



def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (ValueError, OSError):
        return False


def assert_safe_test_execution(
    base_url: str,
    token_file: Path,
    *,
    production_simulation_confirm: str = "",
) -> None:
    errors = collect_environment_errors(config, require_enabled=True)
    root = ROOT.resolve(strict=False)
    db_file = Path(config.DB_FILE).resolve(strict=False)
    token_file = token_file.resolve(strict=False)
    simulation_allowed = production_simulation_confirm == "ALLOW-PRODVERIFY-DESTRUCTIVE-TEST"

    if simulation_allowed:
        if "prodverify" not in root.name.lower():
            errors.append("生产模拟破坏性测试仅允许在目录名包含 prodverify 的隔离副本执行")
        parsed = urlsplit(base_url)
        if (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
            errors.append("生产模拟破坏性测试只允许访问本机回环地址")
    else:
        if config.DEPLOYMENT_SLOT != "test":
            errors.append("会员测试只能在 DEPLOYMENT_SLOT=test 执行")
        if config.APP_ENV != "development":
            errors.append("会员测试只能在 APP_ENV=development 的测试环境执行")
        if int(config.SERVER_PORT) != 8898:
            errors.append("会员测试环境 SERVER_PORT 必须为 8898")

    if Path(config.BASE_DIR).resolve(strict=False) != root:
        errors.append("config.BASE_DIR 与当前源码目录不一致")
    if not _is_within(db_file, root):
        errors.append("DB_FILE 必须位于当前隔离项目目录内")
    if not _is_within(token_file, root):
        errors.append("STOCK_TEST_TOKEN_FILE 必须位于当前隔离项目目录内")
    if token_file == db_file:
        errors.append("测试 Token 文件不得与数据库文件相同")
    if errors:
        raise RuntimeError("拒绝执行破坏性会员测试: " + "; ".join(errors))


@dataclass
class HttpResult:
    status: int
    payload: Any
    text: str
    elapsed_ms: float


def _request(path: str, token: str = "", method: str = "GET", body: dict | None = None) -> HttpResult:
    url = BASE_URL.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["X-API-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
    except URLError as exc:
        raise RuntimeError(f"无法连接服务 {url}：{exc}") from exc
    elapsed = (time.perf_counter() - started) * 1000
    try:
        payload = json.loads(raw)
    except Exception:
        payload = raw
    return HttpResult(status, payload, raw, elapsed)


def _message(result: HttpResult) -> str:
    if isinstance(result.payload, dict):
        value = result.payload.get("message") or result.payload.get("msg") or ""
        return str(value)
    return str(result.payload)[:160]


def _delete_reserved_test_users() -> None:
    conn = get_conn()
    cur = conn.cursor()
    markers = tuple(TEST_MARKERS.values())
    placeholders = ",".join("?" for _ in markers)
    rows = cur.execute(
        f"SELECT id FROM users WHERE phone IN ({placeholders})",
        markers,
    ).fetchall()
    user_ids = [int(row[0]) for row in rows]
    for user_id in user_ids:
        cur.execute("DELETE FROM usage_logs WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM daily_usage_counters WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM password_reset_requests WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM manual_orders WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM api_keys WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()


def _new_user(kind: str, plan_code: str | None, *, expired: bool = False, disabled: bool = False) -> dict:
    marker = TEST_MARKERS[kind]
    user = create_or_get_user(username=f"test_{kind}", phone=marker)
    token = get_or_create_api_key(int(user["id"]))
    subscription = None
    if plan_code:
        subscription = open_subscription(
            int(user["id"]),
            plan_code,
            remark=f"一键会员权限测试-{kind}",
        )
    conn = get_conn()
    if expired:
        conn.execute(
            "UPDATE subscriptions SET start_time='1999-01-01 00:00:00', expire_time='2000-01-01 00:00:00' WHERE user_id=?",
            (int(user["id"]),),
        )
    if disabled:
        # API tokens are stored one-way (token_hash + masked placeholder in token).
        # Never try to disable by comparing the returned plaintext token with the
        # api_keys.token column: new-format rows intentionally do not store the
        # plaintext token there.  The reserved test user is newly created and owns
        # exactly one active test key, so user_id is the authoritative selector.
        changed = conn.execute(
            "UPDATE api_keys SET status='disabled' WHERE user_id=? AND status='active'",
            (int(user["id"]),),
        ).rowcount
        if int(changed or 0) < 1:
            conn.rollback()
            raise RuntimeError("无法禁用保留测试用户Token：未找到active api_key")
    conn.commit()
    if disabled:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active, "
            "SUM(CASE WHEN status='disabled' THEN 1 ELSE 0 END) AS disabled "
            "FROM api_keys WHERE user_id=?",
            (int(user["id"]),),
        ).fetchone()
        if not row or int(row["active"] or 0) != 0 or int(row["disabled"] or 0) < 1:
            raise RuntimeError("禁用Token测试账号准备失败：数据库状态未变为disabled")
        # Clear shared Redis auth context defensively.  In the normal preparation
        # flow the disabled token has not been authenticated yet, but this makes
        # repeated/diagnostic runs deterministic without weakening auth caching.
        try:
            from services.auth_context_cache import clear_user_auth_context_cache
            clear_user_auth_context_cache(int(user["id"]))
        except Exception:
            pass
    return {"user": user, "token": token, "subscription": subscription}


def _prepare_test_accounts(token_file: Path | None = None) -> dict[str, dict]:
    init_db()
    # This is the current module path. It also updates existing plan scopes/quotas.
    ensure_default_plans(update_existing=True)
    _delete_reserved_test_users()
    accounts = {
        "general": _new_user("general", "general_month"),
        "special": _new_user("special", "special_month"),
        "admin": _new_user("admin", "admin_internal"),
        "expired": _new_user("expired", "general_month", expired=True),
        "disabled": _new_user("disabled", "special_month", disabled=True),
        "unsubscribed": _new_user("unsubscribed", None),
    }
    output = resolve_token_file(token_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({key: value["token"] for key, value in accounts.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return accounts


def _print_plans() -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT plan_code, plan_name, plan_type, duration_days, quota_daily,
               quota_per_minute, max_symbols_per_request, min_refresh_interval_sec, scopes
        FROM plans WHERE status='active' ORDER BY id
        """
    ).fetchall()
    print("\n当前套餐：")
    for row in rows:
        try:
            scopes = json.loads(row["scopes"] or "[]")
        except Exception:
            scopes = []
        print(
            f"  {row['plan_code']:<18} | {row['plan_name']:<12} | "
            f"每日={row['quota_daily']:<6} | 每分钟={row['quota_per_minute']:<5} | "
            f"单次股票={row['max_symbols_per_request']:<4} | scopes={len(scopes)}"
        )
    conn.close()


def _direct_scope_check(accounts: dict[str, dict]) -> None:
    from middleware.auth import AuthError, resolve_auth_context

    print("\n数据库直接权限检查：")
    checks = [
        ("general", "tushare:points15000:read"),
        ("general", "market:kaipanla:read"),
        ("general", "admin:sync"),
        ("special", "tushare:points15000:read"),
        ("special", "market:kaipanla:read"),
        ("special", "admin:sync"),
        ("admin", "tushare:points15000:read"),
        ("admin", "market:kaipanla:read"),
        ("admin", "admin:sync"),
    ]
    contexts: dict[str, dict] = {}
    for role in ("general", "special", "admin"):
        try:
            contexts[role] = resolve_auth_context(accounts[role]["token"])
        except AuthError as exc:
            print(f"  [失败] {role}: {exc.status_code} {exc.message}")
            continue
    for role, scope in checks:
        ctx = contexts.get(role)
        if not ctx:
            continue
        allowed = scope_allowed(scope, ctx["scopes"])
        print(f"  {role:<8} {scope:<24} => {allowed}")


def _run_http_tests(accounts: dict[str, dict]) -> tuple[int, int]:
    tests = [
        ("服务存活", "/ping", "", 200),
        ("无Token", "/api/v1/market/tushare/catalog", "", 401),
        ("错误Token", "/api/v1/market/tushare/catalog", "invalid-token-abc", 401),
        ("未开通套餐", "/api/v1/market/tushare/catalog", accounts["unsubscribed"]["token"], 402),
        ("套餐已过期", "/api/v1/market/tushare/catalog", accounts["expired"]["token"], 402),
        ("Token已禁用", "/api/v1/market/tushare/catalog", accounts["disabled"]["token"], 401),
        ("通用套餐访问Tushare", "/api/v1/market/tushare/catalog", accounts["general"]["token"], 200),
        ("通用套餐访问开盘啦", "/api/v1/market/kaipanla/catalog", accounts["general"]["token"], 403),
        ("特殊套餐访问Tushare", "/api/v1/market/tushare/catalog", accounts["special"]["token"], 200),
        ("特殊套餐访问开盘啦", "/api/v1/market/kaipanla/catalog", accounts["special"]["token"], 200),
        ("特殊套餐访问管理员接口", "/api/v1/market/cache/stats", accounts["special"]["token"], 403),
        ("管理员访问管理员接口", "/api/v1/market/cache/stats", accounts["admin"]["token"], 200),
    ]
    passed = 0
    failed = 0
    print("\nHTTP会员权限测试：")
    for title, path, token, expected in tests:
        try:
            result = _request(path, token)
            ok = result.status == expected
            if ok:
                passed += 1
            else:
                failed += 1
            state = "通过" if ok else "失败"
            print(
                f"  [{state}] {title:<22} HTTP={result.status} 预期={expected} "
                f"耗时={result.elapsed_ms:.1f}ms {_message(result)}"
            )
        except Exception as exc:
            failed += 1
            print(f"  [失败] {title:<22} {exc}")
    return passed, failed


def _optional_upstream_tests(accounts: dict[str, dict]) -> None:
    print("\n真实上游连通性（不计入会员权限测试结果）：")
    cases = [
        (
            "Tushare健康检查",
            "/api/v1/market/tushare/health",
            accounts["general"]["token"],
            "GET",
            None,
        ),
        (
            "开盘啦早盘竞价",
            "/api/v1/market/kaipanla/morning_bidding",
            accounts["special"]["token"],
            "POST",
            {"st": 20, "index": 0, "order": 1, "pid_type": 0, "b_type": 4},
        ),
    ]
    for title, path, token, method, body in cases:
        try:
            result = _request(path, token, method, body)
            msg = _message(result)
            if result.status in (401, 402, 403):
                verdict = "会员权限未通过"
            elif result.status == 200:
                count = None
                if isinstance(result.payload, dict):
                    pagination = result.payload.get("pagination")
                    if isinstance(pagination, dict):
                        count = pagination.get("returned")
                        if count is None and isinstance(result.payload.get("items"), list):
                            count = len(result.payload["items"])
                    else:
                        count = result.payload.get("count")
                verdict = f"上游成功，count={count}"
            else:
                verdict = "会员权限已通过，但上游/配置返回异常"
            print(f"  {title:<18} HTTP={result.status} {verdict} {msg}")
        except Exception as exc:
            print(f"  {title:<18} 无法测试：{exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="测试会员、订阅状态和接口权限")
    parser.add_argument("--base-url", default=None, help="待测服务地址；默认读取STOCK_TEST_BASE_URL")
    parser.add_argument("--token-file", default=None, help="测试Token输出文件；默认读取STOCK_TEST_TOKEN_FILE")
    parser.add_argument(
        "--production-simulation-confirm",
        default="",
        help="仅隔离的 stock_server_prodverify 副本可传 ALLOW-PRODVERIFY-DESTRUCTIVE-TEST",
    )
    args = parser.parse_args(argv)

    global BASE_URL
    try:
        BASE_URL = resolve_base_url(
            args.base_url,
            allow_local_production_port=(
                args.production_simulation_confirm == "ALLOW-PRODVERIFY-DESTRUCTIVE-TEST"
            ),
        )
        token_file = resolve_token_file(args.token_file)
        assert_safe_test_execution(
            BASE_URL,
            token_file,
            production_simulation_confirm=args.production_simulation_confirm,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"安全门禁失败：{exc}")
        return 2

    print("=" * 78)
    print("stock_server 一键会员等级、订阅状态和接口权限测试")
    print(f"服务地址：{BASE_URL}")
    print(f"当前数据库：{DB_FILE}")
    print(f"测试Token输出：{token_file}")
    print("当前正式接口路径：/api/v1/market/...")
    print("=" * 78)

    try:
        accounts = _prepare_test_accounts(token_file)
    except Exception as exc:
        print(f"\n创建测试会员失败：{exc}")
        return 2

    _print_plans()
    _direct_scope_check(accounts)

    try:
        ping = _request("/ping")
        if ping.status != 200:
            print(f"\n服务未正常响应：HTTP {ping.status}")
            return 3
    except Exception as exc:
        print("\n无法连接已经启动的服务。")
        print("请先在另一个PowerShell窗口运行：python run_waitress.py")
        print(f"详情：{exc}")
        return 3

    passed, failed = _run_http_tests(accounts)
    _optional_upstream_tests(accounts)

    print("\n" + "=" * 78)
    print(f"会员权限测试完成：通过 {passed}，失败 {failed}")
    print(f"测试Token已保存：{token_file}")
    print("保留的测试用户手机号均以 __MEMBERSHIP_TEST_ 开头，可在后台识别。")
    print("注意：真实上游测试失败不等于会员权限失败，需结合HTTP状态码判断。")
    print("=" * 78)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
