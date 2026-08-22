# -*- coding: utf-8 -*-
"""Verify that the market-data optimization patch is installed correctly."""
from __future__ import annotations

import compileall
import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    ROOT / "services" / "market_data_cache.py",
    ROOT / "services" / "market_data_service.py",
    ROOT / "routes" / "market_data_routes.py",
    ROOT / "integrations" / "market_data" / "tushare" / "catalog.py",
    ROOT / "tools" / "interface_tester.py",
    ROOT / "e2e_tests" / "core" / "all_data_interfaces_test.py",
]

TEST_MODULES = [
    "tests.test_market_data_cache",
    "tests.test_market_data_resilience",
    "tests.test_interface_test_params",
    "tests.test_provider_registry",
    "tests.test_unified_market_routes",
    "tests.test_tushare_catalog",
    "tests.test_tushare_client",
]


def fail(message: str) -> int:
    print(f"[失败] {message}")
    return 1


def main() -> int:
    print(f"项目根目录：{ROOT}")
    print(f"Python：{sys.executable}")

    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.is_file()]
    if missing:
        return fail("缺少补丁文件：" + ", ".join(missing))
    print("[通过] 核心补丁文件均存在")

    test_script = (ROOT / "e2e_tests" / "core" / "all_data_interfaces_test.py").read_text(
        encoding="utf-8"
    )
    required_markers = [
        "测试模式：",
        "强制上游（管理员旁路缓存）",
        "build_sample_param_candidates",
        "TRANSIENT_RETRIES",
    ]
    absent = [marker for marker in required_markers if marker not in test_script]
    if absent:
        return fail(
            "全量接口测试脚本仍是旧版，缺少标记：" + ", ".join(absent)
            + "。请重新覆盖 e2e_tests/core/all_data_interfaces_test.py。"
        )
    print("[通过] 全量接口测试脚本为优化版")

    cache_text = (ROOT / "services" / "market_data_cache.py").read_text(encoding="utf-8")
    for marker in ["stale_if_error_seconds", "allow_stale", "MARKET_DATA_EMPTY_CACHE_TTL_SECONDS"]:
        if marker not in cache_text:
            return fail(f"缓存实现缺少关键标记：{marker}")
    print("[通过] 分级缓存、空结果短缓存和旧数据兜底代码存在")

    compile_targets = [
        ROOT / "config.py",
        ROOT / "app.py",
        ROOT / "services",
        ROOT / "routes",
        ROOT / "integrations",
        ROOT / "tools",
        ROOT / "e2e_tests" / "core",
        ROOT / "tests",
    ]
    ok = True
    for target in compile_targets:
        if target.is_dir():
            ok = compileall.compile_dir(str(target), quiet=1, force=False) and ok
        elif target.is_file():
            ok = compileall.compile_file(str(target), quiet=1, force=False) and ok
    if not ok:
        return fail("Python 编译检查未通过")
    print("[通过] Python 编译检查")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    existing_tests = []
    missing_tests = []
    for module in TEST_MODULES:
        module_path = ROOT / Path(*module.split(".")).with_suffix(".py")
        if module_path.is_file():
            existing_tests.append(module)
        else:
            missing_tests.append(module)
    if missing_tests:
        print("[提示] 当前项目未包含这些可选测试模块：" + ", ".join(missing_tests))
    if existing_tests:
        command = [sys.executable, "-m", "unittest", *existing_tests]
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if completed.returncode != 0:
            return fail("单元测试未通过")
        print(f"[通过] 单元测试：{len(existing_tests)} 个测试模块")

    sys.path.insert(0, str(ROOT))
    config = importlib.import_module("config")
    print("\n当前有效缓存配置：")
    print("  MARKET_DATA_CACHE_ENABLED =", config.MARKET_DATA_CACHE_ENABLED)
    print("  MARKET_DATA_CACHE_TTL_SECONDS =", config.MARKET_DATA_CACHE_TTL_SECONDS)
    print("  MARKET_DATA_EMPTY_CACHE_TTL_SECONDS =", config.MARKET_DATA_EMPTY_CACHE_TTL_SECONDS)
    print("  stock_company TTL =", config.MARKET_DATA_CACHE_TTL_OVERRIDES.get("stock_company"))
    print("  background refresh =", config.MARKET_DATA_BACKGROUND_REFRESH_ENABLED)
    print("  background APIs =", config.MARKET_DATA_BACKGROUND_REFRESH_APIS)
    print("  prewarm =", config.MARKET_DATA_PREWARM_ENABLED)
    print("  prewarm APIs =", config.MARKET_DATA_PREWARM_APIS)
    print("  cache excludes =", config.MARKET_DATA_CACHE_EXCLUDE_APIS)

    expected_excludes = {
        "rt_k", "rt_min", "rt_min_daily", "rt_idx_k", "rt_idx_min",
        "rt_etf_k", "rt_etf_min", "rt_etf_min_daily", "rt_etf_sz_iopv", "rt_sw_k",
    }
    missing_excludes = sorted(expected_excludes - set(config.MARKET_DATA_CACHE_EXCLUDE_APIS))
    if missing_excludes:
        return fail("实时接口缓存排除缺失：" + ", ".join(missing_excludes))
    if config.MARKET_DATA_CACHE_TTL_OVERRIDES.get("stock_company") != 86400:
        return fail("stock_company TTL 应为 86400 秒")
    if config.MARKET_DATA_EMPTY_CACHE_TTL_SECONDS != 45:
        return fail("空结果缓存 TTL 应为 45 秒")

    print("\n[通过] 行情缓存、测试参数、旁路缓存验收和目录结构验证全部完成")
    print("提示：重启服务后，全量测试开头应显示“测试模式：强制上游（管理员旁路缓存）”。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
