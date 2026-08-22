# -*- coding: utf-8 -*-
"""Safely add/update market-data optimization settings in .env.

The script never touches TUSHARE_TOKEN, TUSHARE_API_URL, database settings or
membership configuration.  A timestamped backup is created before writing.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

REALTIME_EXCLUDES = [
    "rt_k",
    "rt_min",
    "rt_min_daily",
    "rt_idx_k",
    "rt_idx_min",
    "rt_etf_k",
    "rt_etf_min",
    "rt_etf_min_daily",
    "rt_etf_sz_iopv",
    "rt_sw_k",
    "download_history",
]

SETTINGS = {
    "MARKET_DATA_CACHE_ENABLED": "True",
    "MARKET_DATA_CACHE_TTL_SECONDS": "300",
    "MARKET_DATA_CACHE_TTL_OVERRIDES": (
        "stock_company=86400,stock_basic=21600,trade_cal=86400,"
        "stock_hsgt=21600,stock_st=3600,st=300,stk_managers=21600,"
        "stk_rewards=21600,bse_mapping=86400,etf_basic=21600,"
        "index_classify=21600,index_member_all=21600,income=21600,"
        "balancesheet=21600,cashflow=21600,fina_indicator=21600,"
        "fina_audit=21600,fina_mainbz=21600,disclosure_date=21600"
    ),
    "MARKET_DATA_EMPTY_CACHE_TTL_SECONDS": "45",
    "MARKET_DATA_STALE_IF_ERROR_SECONDS": "604800",
    "MARKET_DATA_STALE_IF_ERROR_APIS": (
        "stock_company,stock_basic,trade_cal,stock_hsgt,stock_st,"
        "bse_mapping,etf_basic,index_classify,index_member_all"
    ),
    "MARKET_DATA_BACKGROUND_REFRESH_ENABLED": "True",
    "MARKET_DATA_BACKGROUND_REFRESH_APIS": "stock_company,stock_basic,trade_cal",
    "MARKET_DATA_BACKGROUND_REFRESH_WORKERS": "2",
    "MARKET_DATA_REFRESH_AHEAD_SECONDS": "60",
    # The uploaded project runs a single Waitress process via python run_waitress.py.
    # This warms stock_company in a daemon thread and does not block startup.
    "MARKET_DATA_PREWARM_ENABLED": "True",
    "MARKET_DATA_PREWARM_DELAY_SECONDS": "3",
    "MARKET_DATA_PREWARM_APIS": "stock_company",
}


def _parse_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    return stripped.split("=", 1)[0].strip()


def main() -> int:
    if not ENV_FILE.exists():
        raise SystemExit(f"未找到 .env：{ENV_FILE}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ENV_FILE.with_name(f".env.before_market_data_optimization_{stamp}")
    shutil.copy2(ENV_FILE, backup)

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    existing_excludes: list[str] = []
    for line in lines:
        if _parse_key(line) == "MARKET_DATA_CACHE_EXCLUDE_APIS":
            existing_excludes = [
                item.strip() for item in line.split("=", 1)[1].split(",") if item.strip()
            ]
            break
    merged_excludes = list(dict.fromkeys([*existing_excludes, *REALTIME_EXCLUDES]))
    settings = dict(SETTINGS)
    settings["MARKET_DATA_CACHE_EXCLUDE_APIS"] = ",".join(merged_excludes)

    replaced: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = _parse_key(line)
        if key in settings:
            output.append(f"{key}={settings[key]}")
            replaced.add(key)
        else:
            output.append(line)

    missing = [key for key in settings if key not in replaced]
    if missing:
        output.extend([
            "",
            "# ==================== Market data optimization ====================",
        ])
        output.extend(f"{key}={settings[key]}" for key in missing)

    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    print(f"已更新：{ENV_FILE}")
    print(f"备份文件：{backup}")
    print("未修改 TUSHARE_TOKEN、TUSHARE_API_URL、数据库及会员配置。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
