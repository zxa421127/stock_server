# -*- coding: utf-8 -*-
"""Tushare permission-tier mapping used by application subscriptions.

The project exposes two customer-facing tiers:

* ``15000积分权限``: all Tushare point-based interfaces in the project;
* ``单独权限``: interfaces that Tushare lists as separately authorized.

The independent tier is split internally into history/realtime/special scopes so
legacy history plans can keep their original behaviour while the new full plan
can grant all independent permissions with the prefix wildcard
``tushare:independent:*``.
"""
from __future__ import annotations

TUSHARE_CATALOG_SCOPE = "tushare:read"
TUSHARE_POINTS_15000_SCOPE = "tushare:points15000:read"
TUSHARE_INDEPENDENT_HISTORY_SCOPE = "tushare:independent:history:read"
TUSHARE_INDEPENDENT_REALTIME_SCOPE = "tushare:independent:realtime:read"
TUSHARE_INDEPENDENT_SPECIAL_SCOPE = "tushare:independent:special:read"
TUSHARE_INDEPENDENT_WILDCARD_SCOPE = "tushare:independent:*"

INDEPENDENT_HISTORY_APIS = frozenset({
    "etf_mins",
    "idx_mins",
    "sw_mins",
    "stk_mins",
})

INDEPENDENT_REALTIME_APIS = frozenset({
    "rt_etf_k",
    "rt_etf_min",
    "rt_etf_min_daily",
    "rt_etf_sz_iopv",
    "rt_idx_k",
    "rt_idx_min",
    "rt_sw_k",
    "rt_k",
    "rt_min",
    "rt_min_daily",
})

INDEPENDENT_SPECIAL_APIS = frozenset({
    "stk_premarket",
    "irm_qa_sh",
    "irm_qa_sz",
    "stk_auction_o",
    "stk_auction_c",
})

INDEPENDENT_PERMISSION_APIS = frozenset(
    INDEPENDENT_HISTORY_APIS
    | INDEPENDENT_REALTIME_APIS
    | INDEPENDENT_SPECIAL_APIS
)


def permission_class_for_api(api_name: str) -> str:
    """Return the customer-facing permission class for one canonical API name."""
    normalized = (api_name or "").strip().lower().replace("-", "_")
    return "单独权限" if normalized in INDEPENDENT_PERMISSION_APIS else "15000积分权限"


def permission_subtype_for_api(api_name: str) -> str:
    """Return a concise independent-permission subtype or the point tier label."""
    normalized = (api_name or "").strip().lower().replace("-", "_")
    if normalized in INDEPENDENT_HISTORY_APIS:
        return "历史分钟独立权限"
    if normalized in INDEPENDENT_REALTIME_APIS:
        return "实时行情独立权限"
    if normalized in INDEPENDENT_SPECIAL_APIS:
        return "特色数据独立权限"
    return "15000积分接口"


def required_scope_for_api(api_name: str) -> str:
    """Map one canonical API name to the application authorization scope."""
    normalized = (api_name or "").strip().lower().replace("-", "_")
    if normalized in INDEPENDENT_HISTORY_APIS:
        return TUSHARE_INDEPENDENT_HISTORY_SCOPE
    if normalized in INDEPENDENT_REALTIME_APIS:
        return TUSHARE_INDEPENDENT_REALTIME_SCOPE
    if normalized in INDEPENDENT_SPECIAL_APIS:
        return TUSHARE_INDEPENDENT_SPECIAL_SCOPE
    return TUSHARE_POINTS_15000_SCOPE
