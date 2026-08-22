# -*- coding: utf-8 -*-
"""stock_server 一键数据接口测试工具。

直接运行：
    python -m tools.interface_tester

也可以双击项目根目录的 run_interface_test.bat。

功能：
1. 测试一条接口；
2. 测试多条接口；
3. 测试某个数据源全部接口；
4. 测试当前服务注册的全部数据接口；
5. 自动生成 CSV 与 JSON 测试报告。

这里使用的是 stock_server 用户 Token（X-API-Token），不是 .env 中的
TUSHARE_TOKEN。
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_BASE_URL = os.getenv("STOCK_TEST_BASE_URL", "").strip().rstrip("/")
TOKEN_FILE = Path(os.getenv("STOCK_INTERFACE_TEST_TOKEN_FILE", str(ROOT / "data-test" / "interface_test_token.txt"))).expanduser()
RESULT_DIR = Path(os.getenv("STOCK_INTERFACE_TEST_RESULT_DIR", str(ROOT / "data-test" / "interface_test_results"))).expanduser()
if not TOKEN_FILE.is_absolute():
    TOKEN_FILE = ROOT / TOKEN_FILE
if not RESULT_DIR.is_absolute():
    RESULT_DIR = ROOT / RESULT_DIR
TOKEN_FILE = TOKEN_FILE.resolve(strict=False)
RESULT_DIR = RESULT_DIR.resolve(strict=False)


def _assert_path_within_project(path: Path, name: str) -> None:
    try:
        path.relative_to(ROOT.resolve(strict=False))
    except (ValueError, OSError) as exc:
        raise RuntimeError(f"{name} 必须位于当前项目目录内：{ROOT.resolve(strict=False)}") from exc


_assert_path_within_project(TOKEN_FILE, "STOCK_INTERFACE_TEST_TOKEN_FILE")
_assert_path_within_project(RESULT_DIR, "STOCK_INTERFACE_TEST_RESULT_DIR")
REQUEST_TIMEOUT = 45.0
ALL_TEST_INTERVAL_SECONDS = 0.08


def validate_interface_test_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    if not raw:
        raise ValueError("必须显式设置或输入测试服务地址")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"服务地址格式无效：{raw}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("服务地址只能填写协议、主机和端口，不能包含账号、路径、查询参数或片段")
    host = parsed.hostname.lower()
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    test_target = (loopback and port == 8898) or (
        host == "test-api.lifesupermarket.cn"
        and parsed.scheme.lower() == "https"
        and port == 443
    )
    production_target = (loopback and port == 8899) or (
        host == "api.lifesupermarket.cn"
        and parsed.scheme.lower() == "https"
        and port == 443
    )
    if test_target:
        return raw
    if production_target:
        if os.getenv("STOCK_TEST_PRODUCTION_CONFIRM", "") != "ALLOW-PRODUCTION-INTERFACE-TEST":
            raise ValueError(
                "拒绝对生产地址执行接口测试；维护窗口必须显式设置 "
                "STOCK_TEST_PRODUCTION_CONFIRM=ALLOW-PRODUCTION-INTERFACE-TEST"
            )
        return raw
    raise ValueError(
        "接口测试只允许本机 8898、test-api.lifesupermarket.cn；"
        "维护窗口确认后才允许本机 8899 或 api.lifesupermarket.cn"
    )


# ---------- 日期与通用测试值 ----------
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MINUTE = 30


def _last_weekday(day: date | None = None) -> date:
    result = day or date.today()
    while result.weekday() >= 5:
        result -= timedelta(days=1)
    return result


def _as_shanghai_time(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(_SHANGHAI_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=_SHANGHAI_TZ)
    return now.astimezone(_SHANGHAI_TZ)


def get_last_completed_weekday(now: datetime | None = None) -> date:
    """Return the latest weekday whose regular session has finished in Shanghai time.

    This deliberately avoids querying the API under test.  Weekends are skipped;
    exchange holidays can be overridden by running the test on a known completed
    date through the existing sample-parameter editing flow.
    """
    current = _as_shanghai_time(now)
    candidate = current.date()
    before_close = (current.hour, current.minute, current.second) < (
        _MARKET_CLOSE_HOUR,
        _MARKET_CLOSE_MINUTE,
        0,
    )
    if candidate.weekday() >= 5 or before_close:
        candidate -= timedelta(days=1)
    return _last_weekday(candidate)


def _test_dates(now: datetime | None = None) -> dict[str, str]:
    end = get_last_completed_weekday(now)
    start_30 = end - timedelta(days=30)
    start_120 = end - timedelta(days=120)
    start_365 = end - timedelta(days=365)
    previous_year = end.year - 1
    return {
        "trade_date": end.strftime("%Y%m%d"),
        "start_30": start_30.strftime("%Y%m%d"),
        "start_120": start_120.strftime("%Y%m%d"),
        "start_365": start_365.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "month": end.strftime("%Y%m"),
        "period": f"{previous_year}1231",
        "year": str(previous_year),
        "mini_start": start_30.strftime("%Y%m%d"),
        "mini_end": end.strftime("%Y%m%d"),
        "minute_start": end.strftime("%Y-%m-%d 09:00:00"),
        "minute_end": end.strftime("%Y-%m-%d 15:30:00"),
    }


# ---------- 每个接口的内置示例参数 ----------
# 这些参数用于“连通性 + 返回数据”测试。上游没有权限、当前无数据或接口规则变更时，
# 脚本会把结果归类，不会把所有非 200 都误判为本地代码故障。
def build_sample_params(
    provider: str,
    api_name: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    provider = provider.strip().lower()
    api = api_name.strip().lower().replace("-", "_")
    d = _test_dates(now)

    if provider == "kaipanla":
        return {"order": 1, "st": 20, "index": 0, "pid_type": 0, "b_type": 4}

    if provider == "miniqmt":
        if api == "quote":
            return {"symbols": ["000001.SZ"]}
        if api == "download_history":
            return {
                "symbols": ["000001.SZ"],
                "period": "1d",
                "start_time": d["mini_start"],
                "end_time": d["mini_end"],
            }
        return {
            "symbols": ["000001.SZ"],
            "period": "1d",
            "start_time": d["mini_start"],
            "end_time": d["mini_end"],
            "count": 20,
        }

    # Tushare 常用代码
    stock = "000001.SZ"
    index = "000001.SH"
    sw_index = "801010.SI"
    etf = "510300.SH"
    etf_sz = "159919.SZ"

    exact: dict[str, dict[str, Any]] = {
        # 股票基础数据
        "stock_basic": {"list_status": "L", "fields": "ts_code,symbol,name,market,list_status,list_date"},
        "stk_premarket": {"trade_date": d["trade_date"]},
        "trade_cal": {"exchange": "SSE", "start_date": d["start_30"], "end_date": d["end"]},
        "stock_st": {"trade_date": d["trade_date"]},
        "st": {},
        "stock_hsgt": {},
        "namechange": {"ts_code": stock, "start_date": d["start_365"], "end_date": d["end"]},
        "stock_company": {
            "exchange": "SZSE",
            "fields": "ts_code,chairman,manager,province,city,employees,main_business",
        },
        "stk_managers": {"ts_code": stock},
        "stk_rewards": {"ts_code": stock},
        "bse_mapping": {},
        "new_share": {"start_date": d["start_120"], "end_date": d["end"]},
        "bak_basic": {"trade_date": d["trade_date"]},

        # 股票行情
        "daily": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "weekly": {"ts_code": stock, "start_date": d["start_120"], "end_date": d["end"]},
        "monthly": {"ts_code": stock, "start_date": d["start_365"], "end_date": d["end"]},
        "adj_factor": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "daily_basic": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "pro_bar": {"ts_code": stock, "asset": "E", "freq": "D", "start_date": d["start_30"], "end_date": d["end"]},
        "stk_limit": {"trade_date": d["trade_date"]},
        "suspend_d": {"trade_date": d["trade_date"]},
        "hsgt_top10": {"trade_date": d["trade_date"]},
        "ggt_top10": {"trade_date": d["trade_date"]},
        "ggt_daily": {"start_date": d["start_30"], "end_date": d["end"]},
        "bak_daily": {"trade_date": d["trade_date"]},
        "stk_mins": {"ts_code": stock, "freq": "1min", "start_date": d["minute_start"], "end_date": d["minute_end"]},
        "rt_k": {"ts_code": stock},
        "rt_min": {"ts_code": stock, "freq": "1MIN"},
        "rt_min_daily": {"ts_code": stock, "freq": "1MIN"},

        # 财务数据
        "income": {"ts_code": stock, "period": d["period"]},
        "balancesheet": {"ts_code": stock, "period": d["period"]},
        "cashflow": {"ts_code": stock, "period": d["period"]},
        "forecast": {"period": d["period"]},
        "express": {"period": d["period"]},
        "dividend": {"ts_code": stock},
        "fina_indicator": {"ts_code": stock, "period": d["period"]},
        "fina_audit": {"ts_code": stock, "period": d["period"]},
        "fina_mainbz": {"ts_code": stock, "period": d["period"]},
        "disclosure_date": {"end_date": d["period"]},

        # 参考数据
        "stk_shock": {"trade_date": d["trade_date"]},
        "stk_high_shock": {"trade_date": d["trade_date"]},
        "stk_alert": {"trade_date": d["trade_date"]},
        "top10_holders": {"ts_code": stock, "period": d["period"]},
        "top10_floatholders": {"ts_code": stock, "period": d["period"]},
        "pledge_stat": {"ts_code": stock},
        "pledge_detail": {"ts_code": "000014.SZ"},
        "repurchase": {"start_date": d["start_365"], "end_date": d["end"]},
        # Keep the default one-off test bounded as well: share_float may return
        # up to 6000 rows upstream, while stock_server intentionally caps one
        # response at 5000 rows.  20211221 is a documented historical float
        # date with data and keeps the sample deterministic.
        "share_float": {"start_date": "20211221", "end_date": "20211221"},
        "block_trade": {"trade_date": d["trade_date"]},
        "stk_account": {"start_date": "20150101", "end_date": "20171231"},
        "stk_account_old": {"start_date": "20140101", "end_date": "20141231"},
        "stk_holdernumber": {"ts_code": stock},
        "stk_holdertrade": {"start_date": d["start_365"], "end_date": d["end"]},

        # 特色数据
        "report_rc": {"ts_code": stock, "start_date": d["start_365"], "end_date": d["end"]},
        "cyq_perf": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "cyq_chips": {"ts_code": stock, "trade_date": d["trade_date"]},
        "stk_factor": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "stk_factor_pro": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "ccass_hold": {"trade_date": d["trade_date"]},
        "ccass_hold_detail": {"trade_date": d["trade_date"]},
        "hk_hold": {"trade_date": d["trade_date"], "exchange": "HK"},
        "stk_auction_o": {"trade_date": d["trade_date"]},
        "stk_auction_c": {"trade_date": d["trade_date"]},
        "stk_nineturn": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "stk_ah_comparison": {},
        "irm_qa_sh": {"ts_code": "600000.SH", "start_date": d["start_120"], "end_date": d["end"]},
        "irm_qa_sz": {"ts_code": stock, "start_date": d["start_120"], "end_date": d["end"]},
        "broker_recommend": {"month": d["month"]},

        # 两融、转融通
        "margin": {"trade_date": d["trade_date"]},
        "margin_detail": {"trade_date": d["trade_date"]},
        "margin_secs": {"trade_date": d["trade_date"]},
        "slb_len": {"trade_date": "20230901"},
        "slb_sec": {"trade_date": "20230901"},
        "slb_len_mm": {"trade_date": "20230901"},
        "slb_sec_detail": {"trade_date": "20230901"},

        # 资金流向
        "moneyflow": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "moneyflow_ths": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "moneyflow_dc": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "moneyflow_ind_ths": {"trade_date": d["trade_date"]},
        "moneyflow_ind_dc": {"trade_date": d["trade_date"]},
        "moneyflow_mkt_dc": {"trade_date": d["trade_date"]},
        "moneyflow_hsgt": {"trade_date": d["trade_date"]},

        # 打板专题
        "top_list": {"trade_date": d["trade_date"]},
        "top_inst": {"trade_date": d["trade_date"]},
        "limit_list_ths": {"trade_date": d["trade_date"]},
        "limit_list_d": {"trade_date": d["trade_date"]},
        "limit_step": {"trade_date": d["trade_date"]},
        "limit_cpt_list": {"trade_date": d["trade_date"]},
        "ths_index": {"exchange": "A", "type": "N"},
        "ths_daily": {"trade_date": d["trade_date"]},
        "ths_member": {},
        "dc_index": {},
        "dc_member": {},
        "dc_daily": {"trade_date": d["trade_date"]},
        "hm_list": {},
        "hm_detail": {"trade_date": d["trade_date"]},
        "ths_hot": {"trade_date": d["trade_date"]},
        "dc_hot": {"trade_date": d["trade_date"]},
        "tdx_index": {},
        "tdx_member": {},
        "tdx_daily": {"trade_date": d["trade_date"]},
        "kpl_list": {"trade_date": d["trade_date"]},
        "kpl_concept_cons": {"trade_date": d["trade_date"]},
        "dc_concept": {"trade_date": d["trade_date"]},
        "dc_concept_cons": {"trade_date": d["trade_date"]},

        # ETF
        "etf_basic": {"list_status": "L"},
        "etf_index": {},
        "rt_etf_min": {"ts_code": etf, "freq": "1MIN"},
        "rt_etf_min_daily": {"ts_code": etf, "freq": "1MIN"},
        "etf_mins": {"ts_code": etf, "freq": "1min", "start_date": d["minute_start"], "end_date": d["minute_end"]},
        # 诊断结果表明中转实时源当前对 159919.SZ 有数据，
        # 而 510300.SH / 510050.SH 可能返回 HTTP 200 空数据。
        # 这里只调整验收测试样例，不影响正式业务接口按用户代码查询。
        "rt_etf_k": {"ts_code": etf_sz},
        "fund_daily": {"ts_code": etf, "start_date": d["start_30"], "end_date": d["end"]},
        "fund_adj": {"ts_code": etf, "start_date": d["start_30"], "end_date": d["end"]},
        "etf_share_size": {"trade_date": d["trade_date"]},
        "etf_sh_cons": {"trade_date": d["trade_date"]},
        "etf_sz_cons": {"trade_date": d["trade_date"]},
        "rt_etf_sz_iopv": {"ts_code": etf_sz},
        "idx_anns": {"start_date": d["start_365"], "end_date": d["end"]},

        # 指数
        "index_basic": {"market": "SSE"},
        "index_daily": {"ts_code": index, "start_date": d["start_30"], "end_date": d["end"]},
        "rt_idx_k": {"ts_code": index},
        "rt_idx_min": {"ts_code": index, "freq": "1MIN"},
        "index_weekly": {"ts_code": index, "start_date": d["start_120"], "end_date": d["end"]},
        "idx_mins": {"ts_code": index, "freq": "1min", "start_date": d["minute_start"], "end_date": d["minute_end"]},
        "index_monthly": {"ts_code": index, "start_date": d["start_365"], "end_date": d["end"]},
        "index_weight": {"index_code": "000300.SH", "start_date": d["start_120"], "end_date": d["end"]},
        "index_dailybasic": {"trade_date": d["trade_date"]},
        "index_classify": {"level": "L1", "src": "SW2021"},
        "index_member_all": {"ts_code": stock, "is_new": "Y"},
        "sw_daily": {"ts_code": sw_index, "start_date": d["start_30"], "end_date": d["end"]},
        "rt_sw_k": {"ts_code": sw_index},
        "sw_mins": {"ts_code": sw_index, "freq": "1min", "start_date": d["minute_start"], "end_date": d["minute_end"]},
        "ci_index_member": {},
        "ci_daily": {"start_date": d["start_30"], "end_date": d["end"]},
        "index_global": {"ts_code": "IXIC", "start_date": d["start_30"], "end_date": d["end"]},
        "idx_factor_pro": {"ts_code": index, "start_date": d["start_30"], "end_date": d["end"]},
        "daily_info": {"trade_date": d["trade_date"]},
        "sz_daily_info": {"trade_date": d["trade_date"]},
    }
    tester_aliases = {
        "global_index": "index_global",
        "index_mins": "idx_mins",
        "index_factor_pro": "idx_factor_pro",
        "sw_min": "sw_mins",
        "st_risk_warning": "st",
        "stk_surv": "stk_shock",
        "stk_surv_detail": "stk_high_shock",
        "stk_warn": "stk_alert",
        "hsgt_hold_stock": "hk_hold",
        "ths_limit": "limit_list_ths",
        "limit_list": "limit_list_d",
        "kpl_concept": "kpl_concept_cons",
        "dc_thematic": "dc_concept",
        "dc_thematic_detail": "dc_concept_cons",
        "etf_pcf": "etf_sh_cons",
        "etf_pcf_sz": "etf_sz_cons",
        "etf_ref": "rt_etf_sz_iopv",
        "index_ann": "idx_anns",
        "rt_index_k": "rt_idx_k",
        "rt_index_min": "rt_idx_min",
        "index_member": "index_member_all",
        "sw_realtime": "rt_sw_k",
        "index_market": "daily_info",
    }
    api = tester_aliases.get(api, api)
    return dict(exact.get(api, {}))


def build_sample_param_candidates(
    provider: str,
    api_name: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return ordered acceptance-test parameter candidates.

    The acceptance test must stay inside this service's own request/response
    safety contract.  Some upstream APIs can legitimately return 5k-10k rows
    for a broad market-wide query, while stock_server intentionally caps a
    single response at API_MAX_RESPONSE_ROWS (default 5000).  Those APIs use a
    bounded acceptance sample here instead of weakening the production limit.

    Sparse/event/history APIs may still get one or two bounded fallbacks so an
    empty business result is not mistaken for a broken route.
    """
    provider = provider.strip().lower()
    api = api_name.strip().lower().replace("-", "_")
    d = _test_dates(now)
    primary = build_sample_params(provider, api_name, now=now)

    # Kaipanla history is a snapshot/history API.  The generic live-bidding
    # parameters (order/st/index/...) do not bound its output.  limit is a
    # first-class history filter and is applied to either a stored snapshot or
    # the Tushare fallback, keeping the acceptance response below 5000 rows.
    if provider == "kaipanla":
        if api in {"morning_bidding/history", "morning_bidding_history", "bidding_history"}:
            return [{"snapshot_type": "auction", "limit": 20}]
        return [primary]

    if provider != "tushare":
        return [primary]

    stock = "000001.SZ"
    # These are acceptance-only samples.  They deliberately request one symbol,
    # one concept, or a short date window so a healthy high-volume API is not
    # falsely reported as a 413 failure by stock_server's response-size guard.
    bounded_primary: dict[str, dict[str, Any]] = {
        # share_float can legitimately return the upstream maximum (6000 rows)
        # even for a 30-day market-wide window.  The current published project
        # spec accepts start_date/end_date, so use a deterministic one-day
        # historical acceptance sample instead of adding an undeclared query
        # parameter or weakening API_MAX_RESPONSE_ROWS=5000.  Tushare's
        # documented example contains float_date=20211221, making this both
        # bounded and expected to be non-empty.
        "share_float": {"start_date": "20211221", "end_date": "20211221"},
        "bak_basic": {"trade_date": d["trade_date"], "ts_code": stock},
        "stk_premarket": {"trade_date": d["trade_date"], "ts_code": stock},
        "stock_basic": {
            "ts_code": stock,
            "list_status": "L",
            "fields": "ts_code,symbol,name,market,list_status,list_date",
        },
        "dc_member": {"trade_date": d["trade_date"], "ts_code": "BK0145.DC"},
        "ths_member": {"ts_code": "885800.TI"},
        "ccass_hold_detail": {"trade_date": d["trade_date"], "ts_code": "08017.HK"},
        "report_rc": {"ts_code": stock, "start_date": d["start_30"], "end_date": d["end"]},
        "stk_auction_c": {"trade_date": d["trade_date"], "ts_code": stock},
        "stk_auction_o": {"trade_date": d["trade_date"], "ts_code": stock},
        "bak_daily": {"trade_date": d["trade_date"], "ts_code": stock},
        "stk_limit": {"trade_date": d["trade_date"], "ts_code": stock},
        "disclosure_date": {"end_date": d["period"], "ts_code": stock},
    }
    primary = bounded_primary.get(api, primary)

    fallbacks: dict[str, list[dict[str, Any]]] = {
        "etf_index": [{"ts_code": "000300.SH"}],
        # ETF 实时日线的数据覆盖可能因代码和时段不同。验收脚本先用
        # 已实测可返回数据的 159919.SZ；若以后为空，再有限尝试两个
        # 常用沪市 ETF。正式接口不会在用户查询不同代码时自动替换代码。
        "rt_etf_k": [
            {"ts_code": "510300.SH"},
            {"ts_code": "510050.SH"},
        ],
        "st": [{"trade_date": d["trade_date"]}],
        "pledge_detail": [{"ts_code": "000001.SZ"}],
        "stk_holdertrade": [
            {"ann_date": d["trade_date"]},
            {"start_date": d["start_365"], "end_date": d["end"]},
        ],
        # If the bounded current-day CCASS sample is empty, retain a second
        # bounded code/date attempt rather than falling back to an unfiltered
        # market-wide response that can exceed 5000 rows.
        "ccass_hold_detail": [
            {"trade_date": d["trade_date"], "ts_code": "00960.HK"},
        ],
        "express": [
            {"ann_date": d["trade_date"]},
            {"start_date": d["start_365"], "end_date": d["end"]},
        ],
        "forecast": [
            {"ann_date": d["trade_date"]},
            {"start_date": d["start_365"], "end_date": d["end"]},
        ],
        "slb_len": [{"trade_date": "20230630"}, {"trade_date": "20221230"}],
        "slb_len_mm": [{"trade_date": "20230630"}, {"trade_date": "20221230"}],
        "slb_sec": [{"trade_date": "20230630"}, {"trade_date": "20221230"}],
        "slb_sec_detail": [{"trade_date": "20230630"}, {"trade_date": "20221230"}],
        "stk_account": [
            {"start_date": "20160101", "end_date": "20161231"},
            {"start_date": "20140101", "end_date": "20141231"},
        ],
    }
    candidates = [primary, *fallbacks.get(api, [])]
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = json.dumps(candidate, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            seen.add(marker)
            unique.append(dict(candidate))
    return unique


@dataclass(slots=True)
class TestResult:
    provider: str
    api_name: str
    verdict: str
    http_status: int | str
    count: int | str
    cache_hit: bool | str
    elapsed_ms: float
    message: str
    params: str


class InterfaceTester:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Token": token,
            "Accept": "application/json",
            "User-Agent": "stock-server-interface-tester/1.0",
        })

    def _request(self, method: str, path: str, **kwargs: Any) -> tuple[int, dict[str, Any], float]:
        started = time.perf_counter()
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        elapsed = (time.perf_counter() - started) * 1000
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {"success": False, "data": payload, "msg": "返回值不是JSON对象"}
        except Exception:
            payload = {"success": False, "msg": response.text[:1000]}
        return response.status_code, payload, elapsed

    def ping(self) -> bool:
        try:
            status, payload, elapsed = self._request("GET", "/ping")
            ok = status < 400
            print(f"服务连接：{'正常' if ok else '失败'}  HTTP={status}  {elapsed:.1f}ms")
            if not ok:
                print(payload)
            return ok
        except requests.RequestException as exc:
            print(f"无法连接服务：{exc}")
            print("请先在另一个窗口运行：python run_waitress.py")
            return False

    def providers(self) -> list[str]:
        try:
            status, payload, _ = self._request("GET", "/api/v1/market/providers")
        except requests.RequestException as exc:
            print(f"读取数据源失败：{exc}")
            return []
        if status >= 400:
            print(f"读取数据源失败 HTTP={status}：{_message(payload)}")
            return []
        rows = payload.get("data") or []
        return [str(row.get("code", "")).strip() for row in rows if row.get("code")]

    def catalog(self, provider: str) -> list[dict[str, Any]]:
        try:
            status, payload, _ = self._request("GET", f"/api/v1/market/{provider}/catalog")
        except requests.RequestException as exc:
            print(f"读取 {provider} 接口目录失败：{exc}")
            return []
        if status >= 400:
            print(f"读取 {provider} 接口目录失败 HTTP={status}：{_message(payload)}")
            return []
        return list(payload.get("data") or [])

    def health(self, provider: str) -> None:
        try:
            status, payload, elapsed = self._request("GET", f"/api/v1/market/{provider}/health")
            print(f"{provider:10s} HTTP={status} {elapsed:.1f}ms  {_message(payload)}")
            data = payload.get("data")
            if isinstance(data, dict):
                print("  " + json.dumps(data, ensure_ascii=False))
        except requests.RequestException as exc:
            print(f"{provider:10s} NETWORK_ERROR {exc}")

    def test_one(self, provider: str, api_name: str, params: dict[str, Any] | None = None) -> TestResult:
        params = dict(params if params is not None else build_sample_params(provider, api_name))
        path = f"/api/v1/market/{provider}/{api_name}"
        try:
            status, payload, elapsed = self._request("POST", path, json=params)
            items = payload.get("items") if isinstance(payload, dict) else None
            pagination = payload.get("pagination") if isinstance(payload, dict) else None
            count = pagination.get("returned") if isinstance(pagination, dict) else None
            if count is None and isinstance(items, list):
                count = len(items)
            verdict = classify(status, payload, count)
            source = payload.get("source") or {}
            result = TestResult(
                provider=provider,
                api_name=api_name,
                verdict=verdict,
                http_status=status,
                count=count if count is not None else "",
                cache_hit=source.get("cache_hit", ""),
                elapsed_ms=round(elapsed, 2),
                message=_message(payload),
                params=json.dumps(params, ensure_ascii=False, separators=(",", ":")),
            )
        except requests.RequestException as exc:
            result = TestResult(
                provider=provider,
                api_name=api_name,
                verdict="网络失败",
                http_status="",
                count="",
                cache_hit="",
                elapsed_ms=0,
                message=str(exc),
                params=json.dumps(params, ensure_ascii=False, separators=(",", ":")),
            )
        print_result(result)
        return result


def _message(payload: dict[str, Any]) -> str:
    return str(payload.get("msg") or payload.get("message") or payload.get("error") or "")


def classify(status: int, payload: dict[str, Any], count: Any) -> str:
    success = status < 400 and bool(payload.get("success", True))
    if success and isinstance(count, int) and count > 0:
        return "有数据"
    if success:
        return "成功但为空"
    if status == 401:
        return "Token无效"
    if status == 402:
        return "未开套餐"
    if status == 403:
        return "套餐无权限"
    if status == 404:
        return "接口不存在"
    if status == 429:
        return "触发限流"
    if status == 502:
        text = _message(payload).lower()
        if any(word in text for word in ("权限", "积分", "permission", "privilege")):
            return "上游无权限"
        return "上游调用失败"
    if status == 503:
        return "数据源不可用"
    return "失败"


def print_result(result: TestResult) -> None:
    count_text = f" count={result.count}" if result.count != "" else ""
    cache_text = f" cache={result.cache_hit}" if result.cache_hit != "" else ""
    msg = result.message.replace("\n", " ")[:180]
    print(
        f"[{result.verdict:8s}] {result.provider}.{result.api_name} "
        f"HTTP={result.http_status}{count_text}{cache_text} "
        f"{result.elapsed_ms:.1f}ms {msg}"
    )


def save_results(results: list[TestResult]) -> tuple[Path, Path]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULT_DIR / f"interface_test_{stamp}.csv"
    json_path = RESULT_DIR / f"interface_test_{stamp}.json"
    rows = [asdict(item) for item in results]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [
            "provider", "api_name", "verdict", "http_status", "count", "cache_hit",
            "elapsed_ms", "message", "params",
        ])
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def print_summary(results: list[TestResult]) -> None:
    totals: dict[str, int] = {}
    for item in results:
        totals[item.verdict] = totals.get(item.verdict, 0) + 1
    print("\n" + "=" * 72)
    print(f"测试完成：共 {len(results)} 条")
    for verdict, count in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {verdict}: {count}")
    if results:
        csv_path, json_path = save_results(results)
        print(f"CSV报告：{csv_path.resolve()}")
        print(f"JSON报告：{json_path.resolve()}")
    print("=" * 72)


def _normalize_ref(text: str, default_provider: str = "tushare") -> tuple[str, str]:
    value = text.strip()
    if "." in value:
        provider, api = value.split(".", 1)
        return provider.strip().lower(), api.strip().lower().replace("-", "_")
    if "/" in value:
        provider, api = value.split("/", 1)
        return provider.strip().lower(), api.strip().lower().replace("-", "_")
    api = value.lower().replace("-", "_")
    if api == "morning_bidding":
        return "kaipanla", api
    if api in {"history", "quote", "download_history"}:
        return "miniqmt", api
    return default_provider, api


def choose_custom_params(provider: str, api_name: str) -> dict[str, Any]:
    preset = build_sample_params(provider, api_name)
    print("内置测试参数：" + json.dumps(preset, ensure_ascii=False))
    raw = input("直接回车使用内置参数；也可粘贴自定义JSON：").strip()
    if not raw:
        return preset
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("必须是JSON对象")
        return value
    except Exception as exc:
        print(f"JSON无效，改用内置参数：{exc}")
        return preset


def load_token() -> str:
    env_token = os.getenv("STOCK_SERVER_API_TOKEN", "").strip()
    if env_token:
        return env_token
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = input("请输入 stock_server 用户 Token（X-API-Token）：").strip()
    if not token:
        return ""
    save = input("是否仅保存在本机 data/interface_test_token.txt，方便下次使用？[Y/n]：").strip().lower()
    if save not in {"n", "no"}:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def list_catalog(tester: InterfaceTester, providers: Iterable[str]) -> None:
    for provider in providers:
        rows = tester.catalog(provider)
        print(f"\n[{provider}] 共 {len(rows)} 条")
        for row in rows:
            api = row.get("api_name", "")
            title = row.get("title", "")
            realtime = "实时" if row.get("realtime") else ""
            print(f"  {provider}.{api:28s} {title} {realtime}")


def test_refs(tester: InterfaceTester, refs: Iterable[tuple[str, str]], *, interval: float = 0) -> list[TestResult]:
    results: list[TestResult] = []
    for provider, api in refs:
        results.append(tester.test_one(provider, api))
        if interval > 0:
            time.sleep(interval)
        if results[-1].verdict == "触发限流":
            answer = input("已触发限流。是否继续？[y/N]：").strip().lower()
            if answer not in {"y", "yes"}:
                break
    return results


# Imported by executable test-suite scripts; prevent pytest from treating it as a fixture-based test.
test_refs.__test__ = False


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 72)
    print("stock_server 一键数据接口测试")
    print("请先运行 run_waitress.py，再运行本工具。")
    print("=" * 72)

    prompt = (
        f"服务器地址，直接回车使用 {DEFAULT_BASE_URL}："
        if DEFAULT_BASE_URL
        else "请输入服务器地址（必须显式填写，例如 http://127.0.0.1:8898）："
    )
    try:
        base_url = validate_interface_test_base_url(input(prompt).strip() or DEFAULT_BASE_URL)
    except ValueError as exc:
        print(f"安全门禁失败：{exc}")
        return 2
    token = load_token()
    if not token:
        print("没有Token，无法测试受保护接口。")
        return 2

    tester = InterfaceTester(base_url, token)
    if not tester.ping():
        return 1

    while True:
        print("\n请选择：")
        print("  1. 查看数据源健康状态")
        print("  2. 查看全部接口名称")
        print("  3. 测试一条接口")
        print("  4. 测试多条接口")
        print("  5. 测试某个数据源的全部接口")
        print("  6. 测试当前服务的全部数据接口")
        print("  7. 删除本机保存的测试Token")
        print("  0. 退出")
        choice = input("输入序号：").strip()

        if choice == "0":
            return 0

        providers = tester.providers()
        if not providers:
            print("无法获取数据源。请检查Token、套餐和服务日志。")
            continue

        if choice == "1":
            for provider in providers:
                tester.health(provider)
            continue

        if choice == "2":
            list_catalog(tester, providers)
            continue

        if choice == "3":
            text = input("输入接口名，例如 daily、tushare.daily、kaipanla.morning_bidding：").strip()
            if not text:
                continue
            provider, api = _normalize_ref(text)
            params = choose_custom_params(provider, api)
            results = [tester.test_one(provider, api, params)]
            print_summary(results)
            continue

        if choice == "4":
            text = input("输入多个接口，用逗号分隔，例如 daily,stock_basic,index_daily：").strip()
            refs = [_normalize_ref(item) for item in text.replace("，", ",").split(",") if item.strip()]
            if not refs:
                continue
            results = test_refs(tester, refs, interval=ALL_TEST_INTERVAL_SECONDS)
            print_summary(results)
            continue

        if choice == "5":
            print("当前数据源：" + ", ".join(providers))
            provider = input("输入数据源名称：").strip().lower()
            if provider not in providers:
                print("数据源不存在或未启用。")
                continue
            rows = tester.catalog(provider)
            refs = [(provider, str(row.get("api_name", ""))) for row in rows if row.get("api_name")]
            confirm = input(f"将测试 {len(refs)} 条接口，可能消耗上游额度。输入 YES 继续：").strip()
            if confirm != "YES":
                print("已取消。")
                continue
            results = test_refs(tester, refs, interval=ALL_TEST_INTERVAL_SECONDS)
            print_summary(results)
            continue

        if choice == "6":
            refs: list[tuple[str, str]] = []
            for provider in providers:
                refs.extend(
                    (provider, str(row.get("api_name", "")))
                    for row in tester.catalog(provider)
                    if row.get("api_name")
                )
            confirm = input(
                f"将逐条测试 {len(refs)} 个接口，可能耗时数分钟并消耗Tushare额度。输入 YES 继续："
            ).strip()
            if confirm != "YES":
                print("已取消。")
                continue
            results = test_refs(tester, refs, interval=ALL_TEST_INTERVAL_SECONDS)
            print_summary(results)
            continue

        if choice == "7":
            try:
                TOKEN_FILE.unlink(missing_ok=True)
                print("已删除 data/interface_test_token.txt。重新运行工具时会再次询问Token。")
            except Exception as exc:
                print(f"删除失败：{exc}")
            continue

        print("序号无效，请重新输入。")


if __name__ == "__main__":
    raise SystemExit(main())
