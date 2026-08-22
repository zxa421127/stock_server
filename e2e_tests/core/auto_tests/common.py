from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

_TEST_PUBLIC_HOST = "test-api.lifesupermarket.cn"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def validate_test_base_url(value: str | None) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        raise RuntimeError("必须显式设置 STOCK_TEST_BASE_URL；禁止使用隐式生产端口默认值")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(f"STOCK_TEST_BASE_URL 格式无效：{raw}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise RuntimeError("STOCK_TEST_BASE_URL 只能填写协议、主机和端口，不能包含账号、路径、查询参数或片段")
    host = parsed.hostname.lower()
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    is_local_test = host in _LOOPBACK_HOSTS and port == 8898
    is_public_test = (
        host == _TEST_PUBLIC_HOST
        and parsed.scheme.lower() == "https"
        and port == 443
    )
    if not (is_local_test or is_public_test):
        raise RuntimeError(
            "E2E 只允许测试实例 http://127.0.0.1:8898、"
            "http://localhost:8898 或 https://test-api.lifesupermarket.cn；"
            f"当前为 {raw}"
        )
    return raw


def _find_project_root() -> Path:
    configured = os.getenv("STOCK_SERVER_ROOT", "").strip()
    if configured:
        return Path(configured)
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "app.py").exists() and (candidate / "requirements.txt").exists():
            return candidate
    return here.parents[1]


ROOT = _find_project_root()

def _resolve_runtime_path(value: str, *, name: str, default: Path) -> Path:
    path = Path(value or str(default)).expanduser().resolve(strict=False)
    root = ROOT.resolve(strict=False)
    try:
        path.relative_to(root)
    except (ValueError, OSError) as exc:
        raise RuntimeError(f"{name} 必须位于当前测试项目目录内：{root}") from exc
    return path

load_dotenv(ROOT / ".env")
BASE_URL = (os.getenv("STOCK_TEST_BASE_URL") or "").strip().rstrip("/")
if BASE_URL:
    BASE_URL = validate_test_base_url(BASE_URL)
RESULT_DIR = _resolve_runtime_path(
    os.getenv("STOCK_TEST_RESULT_DIR", ""),
    name="STOCK_TEST_RESULT_DIR",
    default=ROOT / "data-test" / "auto_test_results",
)
TOKEN_FILE = _resolve_runtime_path(
    os.getenv("STOCK_TEST_TOKEN_FILE", ""),
    name="STOCK_TEST_TOKEN_FILE",
    default=ROOT / "data-test" / "membership_test_tokens.json",
)


@dataclass
class Result:
    group: str
    name: str
    passed: bool
    expected: str
    actual: str
    detail: str = ""


def request(path: str, token: str = "", method: str = "GET", body: dict | None = None, timeout: int = 45):
    if not BASE_URL:
        raise RuntimeError("必须显式设置 STOCK_TEST_BASE_URL")
    headers = {"Accept": "application/json", "User-Agent": "stock-server-auto-tests/1.0"}
    if token:
        headers["X-API-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(BASE_URL + path, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read().decode("utf-8", "replace"), int(resp.status)
    except HTTPError as exc:
        raw, status = exc.read().decode("utf-8", "replace"), int(exc.code)
    except URLError as exc:
        raise RuntimeError(f"无法连接 {BASE_URL}：{exc}") from exc
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"raw": raw[:1000]}
    return status, payload, round((time.perf_counter() - started) * 1000, 1)


def load_tokens() -> dict[str, str]:
    """Load membership test tokens and normalize old/new tier names.

    The six-plan catalog uses ``general`` and ``special``.  Older test scripts
    and token files used ``history`` and ``realtime``.  Returning aliases in
    both directions keeps previously generated token files usable while all
    current tests use the new names.
    """
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            f"缺少 {TOKEN_FILE}，请先运行 "
            "e2e_tests\\02_account_permissions\\01_prepare_test_accounts.bat"
        )

    raw = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"测试Token文件格式错误：{TOKEN_FILE} 必须是JSON对象")

    tokens = {str(key): str(value) for key, value in raw.items() if value}
    aliases = (("general", "history"), ("special", "realtime"))
    for current_name, legacy_name in aliases:
        if current_name not in tokens and legacy_name in tokens:
            tokens[current_name] = tokens[legacy_name]
        if legacy_name not in tokens and current_name in tokens:
            tokens[legacy_name] = tokens[current_name]

    required = {"general", "special", "admin", "expired", "disabled", "unsubscribed"}
    missing = sorted(required.difference(tokens))
    if missing:
        raise RuntimeError(
            f"测试Token文件缺少角色 {missing}；请重新运行 "
            "e2e_tests\\02_account_permissions\\01_prepare_test_accounts.bat"
        )
    return tokens


def message(payload) -> str:
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("msg") or "")[:300]
    return str(payload)[:300]


def data_evidence(payload, limit: int = 3) -> tuple[int, list]:
    """提取实际数据条数和前几条具体返回数据，供权限报告举证。"""
    if not isinstance(payload, dict):
        return 0, []
    data = payload.get("data")
    if isinstance(data, list):
        return len(data), data[:limit]
    if isinstance(data, dict):
        return (1 if data else 0), ([data] if data else [])
    return 0, []


def compact_json(value, limit: int = 4000) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text[:limit] + ("..." if len(text) > limit else "")


def save_report(title: str, results: list[Result]) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = RESULT_DIR / f"{title}_{stamp}.json"
    summary = {"title": title, "base_url": BASE_URL, "passed": sum(x.passed for x in results),
               "failed": sum(not x.passed for x in results), "results": [asdict(x) for x in results]}
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in results:
        print(f"[{'通过' if item.passed else '失败'}] {item.name} | 预期={item.expected} | 实际={item.actual} {item.detail}")
    print(f"\n汇总：通过 {summary['passed']}，失败 {summary['failed']}")
    print(f"报告：{path}")
    return path
