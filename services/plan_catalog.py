# -*- coding: utf-8 -*-
"""Central permission and subscription-plan catalog.

Public product model:
- General interface plans: 119 Tushare point-based APIs.
- Special permission plans: general APIs + 19 Tushare independent-permission
  APIs + Kaipanla morning_bidding.

Each product supports month, quarter and year durations.  The internal admin
plan is retained for operations and is never exposed as a public product.
"""
from __future__ import annotations

from integrations.market_data.tushare.permissions import (
    TUSHARE_CATALOG_SCOPE,
    TUSHARE_INDEPENDENT_HISTORY_SCOPE,
    TUSHARE_INDEPENDENT_REALTIME_SCOPE,
    TUSHARE_INDEPENDENT_SPECIAL_SCOPE,
    TUSHARE_INDEPENDENT_WILDCARD_SCOPE,
    TUSHARE_POINTS_15000_SCOPE,
)

# 119 Tushare point-based APIs.
GENERAL_SCOPES = [
    TUSHARE_CATALOG_SCOPE,
    TUSHARE_POINTS_15000_SCOPE,
]

# General APIs + 19 independent-permission APIs + Kaipanla.
# MiniQMT and all administrator scopes remain excluded.
SPECIAL_SCOPES = [
    TUSHARE_CATALOG_SCOPE,
    TUSHARE_POINTS_15000_SCOPE,
    TUSHARE_INDEPENDENT_WILDCARD_SCOPE,
    "market:read",
    "market:kaipanla:read",
]

# Compatibility aliases for code that imported the old names.  They no longer
# represent sellable legacy plans; only the six plans in DEFAULT_PLANS do.
DEVELOPER_POINTS_SCOPES = GENERAL_SCOPES
DEVELOPER_FULL_SCOPES = SPECIAL_SCOPES
HISTORY_SCOPES = GENERAL_SCOPES
REALTIME_SCOPES = SPECIAL_SCOPES
MARKET_SCOPES = ["market:read", "market:kaipanla:read"]

ADMIN_SCOPES = [
    "admin:*",
    "admin:sync",
    "admin:member:read",
    "admin:member:write",
]


def _plan(
    *,
    plan_code: str,
    plan_name: str,
    plan_type: str,
    duration_type: str,
    duration_days: int,
    price_cent: int,
    quota_daily: int,
    quota_per_minute: int,
    scopes: list[str],
) -> dict:
    return {
        "plan_code": plan_code,
        "plan_name": plan_name,
        "plan_type": plan_type,
        "duration_type": duration_type,
        "duration_days": duration_days,
        "original_price_cent": price_cent,
        "sale_price_cent": price_cent,
        "quota_daily": quota_daily,
        "quota_per_minute": quota_per_minute,
        "max_symbols_per_request": 100,
        "min_refresh_interval_sec": 0,
        "scopes": scopes,
        "public": True,
    }


# PLATFORM_POLICY_PLAN_CATALOG_V1
# General/Special/Admin plan policy is maintained only in
# settings/platform_policy.json.
from services.platform_policy import (
    expand_plans as _expand_platform_plans,
)

DEFAULT_PLANS = (
    _expand_platform_plans()
)

# Built-in public plans from the previous catalog.  The explicit migration
# maps subscriptions/orders to the new six-plan catalog before deleting them.
LEGACY_PUBLIC_PLAN_MIGRATION = {
    "developer_points_month": "general_month",
    "developer_full_month": "special_month",
    "history_month": "general_month",
    "history_quarter": "general_quarter",
    "history_year": "general_year",
    "realtime_month": "special_month",
    "realtime_quarter": "special_quarter",
    "realtime_year": "special_year",
}


def scope_allowed(required_scope: str, granted_scopes) -> bool:
    """Support exact scopes, global *, and prefix wildcards such as admin:*.

    ``tushare:independent:*`` grants all three independent-permission groups,
    but does not grant the point-based tier.
    """
    if not required_scope:
        return True
    if isinstance(granted_scopes, str):
        granted_scopes = [granted_scopes]
    granted_scopes = granted_scopes or []
    if "*" in granted_scopes or required_scope in granted_scopes:
        return True
    for scope in granted_scopes:
        if isinstance(scope, str) and scope.endswith(":*") and required_scope.startswith(scope[:-1]):
            return True
    return False


def scope_display_name(required_scope: str) -> str:
    labels = {
        TUSHARE_CATALOG_SCOPE: "Tushare接口目录",
        TUSHARE_POINTS_15000_SCOPE: "通用接口（15000积分权限）",
        TUSHARE_INDEPENDENT_HISTORY_SCOPE: "特殊权限：Tushare历史分钟",
        TUSHARE_INDEPENDENT_REALTIME_SCOPE: "特殊权限：Tushare实时行情",
        TUSHARE_INDEPENDENT_SPECIAL_SCOPE: "特殊权限：Tushare特色数据",
        "market:kaipanla:read": "特殊权限：开盘啦接口",
        "market:miniqmt:read": "MiniQMT接口",
    }
    return labels.get(required_scope, required_scope)


def public_plan_codes() -> set[str]:
    return {plan["plan_code"] for plan in DEFAULT_PLANS if plan.get("public")}


def plan_by_code(plan_code: str):
    return next((plan for plan in DEFAULT_PLANS if plan["plan_code"] == plan_code), None)
