# -*- coding: utf-8 -*-
"""
Round 2A - stock_server_test risk policy foundation
ONLY modifies C:\\stockdata\\stock_server_test.

Changes:
- General RPM -> 120; Special RPM -> 300
- MIN_REQUESTS_PER_MINUTE -> 1 (so explicit plan quota is not lifted to 800)
- Global market heavy-query config -> 16
- Adds General/Special concurrency config keys for Round 2B wiring
- Adds per-interface response-row override support
- Adds initial 10,000-row full-market whitelist
- Preserves global default response row cap at 5,000
- Backs up every touched file, including .env, without printing secrets
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\stockdata\stock_server_test")
BACKUP_ROOT = Path(r"C:\stockdata\backups")
REPORT_ROOT = ROOT / "data-test"

TOUCH = [
    ROOT / "config.py",
    ROOT / ".env.example",
    ROOT / ".env",
    ROOT / "services" / "plan_catalog.py",
    ROOT / "routes" / "market_data_routes.py",
    ROOT / "tests" / "test_market_response_limits.py",
]

FULL_MARKET_OVERRIDES = (
    "tushare.stock_basic=10000,"
    "tushare.daily=10000,"
    "tushare.daily_basic=10000,"
    "tushare.stk_limit=10000,"
    "tushare.bak_daily=10000"
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def update_env_key(text: str, key: str, value: str, *, insert_after: str | None = None,
                   comment: str | None = None) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    replacement = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)

    block = replacement if not comment else f"{comment}\n{replacement}"

    if insert_after:
        anchor = re.search(rf"^{re.escape(insert_after)}=.*$", text, re.M)
        if not anchor:
            fail(f"Cannot add {key}: anchor {insert_after} not found")
        return text[:anchor.end()] + "\n\n" + block + text[anchor.end():]

    return text.rstrip() + "\n\n" + block + "\n"


def insert_after_matching_line(text: str, pattern: str, block: str) -> str:
    match = re.search(pattern, text, re.M)
    if not match:
        fail(f"Anchor not found: {pattern}")
    return text[:match.end()] + "\n" + block.rstrip("\n") + text[match.end():]


def replace_quota_near(text: str, plan_code: str, value: int) -> str:
    idx = text.find(plan_code)
    if idx < 0:
        fail(f"Plan code not found: {plan_code}")

    window = text[idx:idx + 2500]
    match = re.search(r'(["\']quota_per_minute["\']\s*:\s*)\d+', window)
    if not match:
        fail(f"quota_per_minute not found near {plan_code}")

    start = idx + match.start()
    end = idx + match.end()
    replacement = match.group(1) + str(value)
    return text[:start] + replacement + text[end:]


def backup_files(stamp: str) -> Path:
    backup_dir = BACKUP_ROOT / f"risk-policy-round2a-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    for source in TOUCH:
        if not source.exists():
            fail(f"Required file missing: {source}")
        rel = source.relative_to(ROOT)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

    return backup_dir


def patch_config(text: str) -> str:
    if "API_MAX_RESPONSE_ROWS_OVERRIDES =" not in text:
        text = insert_after_matching_line(
            text,
            r'^API_MAX_RESPONSE_ROWS\s*=\s*_get_int\("API_MAX_RESPONSE_ROWS".*$',
            'API_MAX_RESPONSE_ROWS_OVERRIDES = _get_int_map(\n'
            '    "API_MAX_RESPONSE_ROWS_OVERRIDES", "", minimum=1, maximum=1_000_000\n'
            ')',
        )

    text, n = re.subn(
        r'^(MARKET_QUERY_MAX_CONCURRENT_GLOBAL\s*=\s*_get_int\('
        r'"MARKET_QUERY_MAX_CONCURRENT_GLOBAL",\s*)(100|16)(,\s*0,\s*100000\))$',
        r'\g<1>16\3',
        text,
        flags=re.M,
    )
    if n != 1:
        fail(f"Expected one MARKET_QUERY_MAX_CONCURRENT_GLOBAL config line, got {n}")

    tier_anchor = "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER"
    if tier_anchor not in text:
        tier_block = '''MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER = _get_int(
    "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER", 2, 0, 1000
)
MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN = _get_int(
    "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN", 2, 0, 1000
)
MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER = _get_int(
    "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER", 4, 0, 1000
)
MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN = _get_int(
    "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN", 4, 0, 1000
)'''
        text = insert_after_matching_line(
            text,
            r"^MARKET_QUERY_MAX_CONCURRENT_GLOBAL\s*=.*$",
            tier_block,
        )

    return text


def patch_env_example(text: str) -> str:
    text = update_env_key(
        text,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        FULL_MARKET_OVERRIDES,
        insert_after="API_MAX_RESPONSE_ROWS",
        comment=(
            "# 单接口响应行数覆盖；全市场/大截面接口可定向放宽。"
            "未列出的接口仍使用 API_MAX_RESPONSE_ROWS。"
        ),
    )

    text = update_env_key(text, "MIN_REQUESTS_PER_MINUTE", "1")
    text = update_env_key(text, "MARKET_QUERY_MAX_CONCURRENT_GLOBAL", "16")

    for key, value in [
        ("MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER", "2"),
        ("MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN", "2"),
        ("MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER", "4"),
        ("MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN", "4"),
    ]:
        text = update_env_key(text, key, value, insert_after="MARKET_QUERY_MAX_CONCURRENT_GLOBAL")

    return text


def patch_real_env(text: str) -> str:
    text = update_env_key(
        text,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        FULL_MARKET_OVERRIDES,
        insert_after="API_MAX_RESPONSE_ROWS",
    )
    text = update_env_key(text, "MIN_REQUESTS_PER_MINUTE", "1")
    text = update_env_key(text, "MARKET_QUERY_MAX_CONCURRENT_GLOBAL", "16")

    for key, value in [
        ("MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER", "2"),
        ("MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN", "2"),
        ("MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER", "4"),
        ("MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN", "4"),
    ]:
        text = update_env_key(text, key, value, insert_after="MARKET_QUERY_MAX_CONCURRENT_GLOBAL")
    return text


def patch_plan_catalog(text: str) -> str:
    for code in ("general_month", "general_quarter", "general_year"):
        text = replace_quota_near(text, code, 120)

    for code in ("special_month", "special_quarter", "special_year"):
        text = replace_quota_near(text, code, 300)

    return text


ROW_LIMIT_HELPER = '''def response_row_limit_for(provider_code: str, data_type: str) -> int:
    """Return an interface-specific row cap without weakening the global default."""
    default_limit = int(getattr(config, "API_MAX_RESPONSE_ROWS", 5000))
    overrides = dict(getattr(config, "API_MAX_RESPONSE_ROWS_OVERRIDES", {}) or {})
    provider = str(provider_code or "").strip().lower().replace("-", "_")
    normalized = (
        str(data_type or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
    )
    for key in (f"{provider}.{normalized}", normalized):
        if key in overrides:
            return max(1, int(overrides[key]))
    return max(1, default_limit)


'''


def patch_market_routes(text: str) -> str:
    if "def response_row_limit_for(" not in text:
        marker = re.search(r"^def enforce_response_limits\(", text, re.M)
        if not marker:
            fail("Cannot find enforce_response_limits()")
        text = text[:marker.start()] + ROW_LIMIT_HELPER + text[marker.start():]

    q_start = text.find("def _query_response(")
    if q_start < 0:
        fail("Cannot find _query_response()")

    next_def = re.search(r"\n(?:def |@)", text[q_start + 1:])
    q_end = q_start + 1 + next_def.start() if next_def else len(text)
    q = text[q_start:q_end]

    if "response_row_limit = response_row_limit_for(provider_code, data_type)" not in q:
        marker = re.search(r"^(\s*)enforce_dataframe_limits\(", q, re.M)
        if not marker:
            fail("Cannot find enforce_dataframe_limits() inside _query_response()")
        indent = marker.group(1)
        q = q[:marker.start()] + f"{indent}response_row_limit = response_row_limit_for(provider_code, data_type)\n" + q[marker.start():]

    q, count = re.subn(
        r'max_rows\s*=\s*int\(getattr\(config,\s*"API_MAX_RESPONSE_ROWS",\s*5000\)\)',
        "max_rows=response_row_limit",
        q,
    )

    if count not in (0, 2):
        fail(f"Unexpected API_MAX_RESPONSE_ROWS replacements inside _query_response(): {count}")

    if q.count("max_rows=response_row_limit") < 2:
        fail("Row override was not wired to both DataFrame and JSON-record limits")

    return text[:q_start] + q + text[q_end:]


TEST_APPEND = r'''

def test_full_market_row_limit_overrides_are_interface_specific(monkeypatch):
    import routes.market_data_routes as routes

    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {
            "tushare.stock_basic": 10000,
            "tushare.daily": 10000,
            "tushare.daily_basic": 10000,
            "tushare.stk_limit": 10000,
            "tushare.bak_daily": 10000,
        },
    )

    assert routes.response_row_limit_for("tushare", "stock_basic") == 10000
    assert routes.response_row_limit_for("tushare", "daily") == 10000
    assert routes.response_row_limit_for("tushare", "daily_basic") == 10000
    assert routes.response_row_limit_for("tushare", "stk_limit") == 10000
    assert routes.response_row_limit_for("tushare", "bak_daily") == 10000
    assert routes.response_row_limit_for("kaipanla", "stock_basic") == 5000
    assert routes.response_row_limit_for("tushare", "income") == 5000
'''


def patch_response_tests(text: str) -> str:
    if "test_full_market_row_limit_overrides_are_interface_specific" not in text:
        text = text.rstrip() + TEST_APPEND + "\n"
    return text


def syntax_check(path: Path) -> None:
    if path.suffix == ".py":
        ast.parse(read(path), filename=str(path))


def main() -> int:
    if Path.cwd().resolve() != ROOT.resolve():
        fail(f"Run this script from {ROOT}; current={Path.cwd()}")

    if not (ROOT / ".venv" / "Scripts" / "python.exe").exists():
        fail("TEST virtualenv not found")

    env_text = read(ROOT / ".env")
    if "DEPLOYMENT_SLOT=test" not in env_text:
        fail("TEST guard failed: .env does not contain DEPLOYMENT_SLOT=test")
    if r"DB_FILE=C:\stockdata\stock_server_test\data\stock_server.db" not in env_text:
        if "DB_FILE=data/stock_server.db" not in env_text and r"DB_FILE=data\stock_server.db" not in env_text:
            fail("TEST guard failed: DB_FILE is not the stock_server_test database")
    if "REDIS_KEY_PREFIX=stock_server_test" not in env_text:
        fail("TEST guard failed: Redis prefix is not stock_server_test")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = backup_files(stamp)

    originals = {path: read(path) for path in TOUCH}
    changed = []

    try:
        new_values = {
            ROOT / "config.py": patch_config(originals[ROOT / "config.py"]),
            ROOT / ".env.example": patch_env_example(originals[ROOT / ".env.example"]),
            ROOT / ".env": patch_real_env(originals[ROOT / ".env"]),
            ROOT / "services" / "plan_catalog.py": patch_plan_catalog(originals[ROOT / "services" / "plan_catalog.py"]),
            ROOT / "routes" / "market_data_routes.py": patch_market_routes(originals[ROOT / "routes" / "market_data_routes.py"]),
            ROOT / "tests" / "test_market_response_limits.py": patch_response_tests(originals[ROOT / "tests" / "test_market_response_limits.py"]),
        }

        for path, new_text in new_values.items():
            if new_text != originals[path]:
                write(path, new_text)
                changed.append(str(path.relative_to(ROOT)))

        for path in new_values:
            syntax_check(path)

    except Exception:
        for source in TOUCH:
            rel = source.relative_to(ROOT)
            backup = backup_dir / rel
            if backup.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, source)
        raise

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report = {
        "round": "2A",
        "root": str(ROOT),
        "backup_dir": str(backup_dir),
        "changed_files": changed,
        "production_modified": False,
        "policy": {
            "general_rpm": 120,
            "special_rpm": 300,
            "minimum_rpm_floor": 1,
            "global_heavy_query_target": 16,
            "http_active_request_hard_limit": None,
            "default_response_rows": 5000,
            "full_market_response_rows": 10000,
        },
    }
    report_path = REPORT_ROOT / f"risk-policy-round2a-{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("ROUND2A_PATCH=PASS")
    print(f"BACKUP_DIR={backup_dir}")
    print("CHANGED_FILES=" + ",".join(changed))
    print(f"REPORT={report_path}")
    print("PRODUCTION_MODIFIED=FALSE")
    print("NEXT=run targeted pytest; do not restart or publish yet")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ROUND2A_PATCH=FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
