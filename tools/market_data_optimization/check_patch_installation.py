# -*- coding: utf-8 -*-
"""Print whether the optimized files are currently active in the project."""
from pathlib import Path
import importlib
import sys

ROOT = Path(__file__).resolve().parents[2]
checks = {
    "优化版全量测试": (ROOT / "e2e_tests/core/all_data_interfaces_test.py", "强制上游（管理员旁路缓存）"),
    "分级缓存": (ROOT / "services/market_data_cache.py", "stale_if_error_seconds"),
    "后台刷新": (ROOT / "services/market_data_service.py", "MARKET_DATA_BACKGROUND_REFRESH_ENABLED"),
    "测试参数候选": (ROOT / "tools/interface_tester.py", "build_sample_param_candidates"),
}
failed = False
for name, (path, marker) in checks.items():
    ok = path.is_file() and marker in path.read_text(encoding="utf-8")
    print(f"{'[通过]' if ok else '[失败]'} {name}: {path.relative_to(ROOT)}")
    failed = failed or not ok
sys.path.insert(0, str(ROOT))
try:
    config = importlib.import_module("config")
    print("stock_company TTL =", config.MARKET_DATA_CACHE_TTL_OVERRIDES.get("stock_company"))
    print("empty cache TTL =", config.MARKET_DATA_EMPTY_CACHE_TTL_SECONDS)
    print("prewarm enabled =", config.MARKET_DATA_PREWARM_ENABLED)
except Exception as exc:
    print("[失败] 无法导入 config:", exc)
    failed = True
raise SystemExit(1 if failed else 0)
