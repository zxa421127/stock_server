# -*- coding: utf-8 -*-
"""Validate the six public plans and their permission boundaries."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_utils import get_conn, get_plan_by_code, init_db, list_active_plans
from integrations.market_data.tushare.catalog import list_tushare_apis
from integrations.market_data.tushare.permissions import (
    INDEPENDENT_PERMISSION_APIS,
    required_scope_for_api,
)
from services.plan_catalog import (
    GENERAL_SCOPES,
    LEGACY_PUBLIC_PLAN_MIGRATION,
    SPECIAL_SCOPES,
    scope_allowed,
)

EXPECTED = {
    "general_month": (4900, 30, "general"),
    "general_quarter": (14700, 90, "general"),
    "general_year": (58800, 365, "general"),
    "special_month": (8900, 30, "special"),
    "special_quarter": (26700, 90, "special"),
    "special_year": (106800, 365, "special"),
}


def _scopes(plan: dict) -> list[str]:
    value = plan.get("scopes") or "[]"
    return json.loads(value) if isinstance(value, str) else list(value)


def main() -> int:
    init_db()

    rows = list_tushare_apis()
    point_rows = [row for row in rows if row["permission_class"] == "15000积分权限"]
    independent_rows = [row for row in rows if row["permission_class"] == "单独权限"]

    active_public = list_active_plans()
    active_codes = {row["plan_code"] for row in active_public}
    if active_codes != set(EXPECTED):
        raise SystemExit(
            f"Public plan codes mismatch: expected={sorted(EXPECTED)} actual={sorted(active_codes)}"
        )

    print("Public plans:")
    for code, (price, days, plan_type) in EXPECTED.items():
        plan = get_plan_by_code(code)
        if not plan:
            raise SystemExit(f"Missing plan: {code}")
        assert int(plan["sale_price_cent"]) == price
        assert int(plan["duration_days"]) == days
        assert plan["plan_type"] == plan_type
        print(
            f"  {code:<18} price={price / 100:>7.2f} "
            f"days={days:<3} type={plan_type}"
        )

    conn = get_conn()
    old_codes = sorted(LEGACY_PUBLIC_PLAN_MIGRATION)
    placeholders = ",".join("?" for _ in old_codes)
    old_rows = conn.execute(
        f"SELECT plan_code FROM plans WHERE plan_code IN ({placeholders})",
        old_codes,
    ).fetchall()
    if old_rows:
        raise SystemExit(f"Legacy plans still exist: {[row['plan_code'] for row in old_rows]}")

    samples = [
        ("point API stock_basic", required_scope_for_api("stock_basic")),
        ("independent history API etf_mins", required_scope_for_api("etf_mins")),
        ("independent realtime API rt_k", required_scope_for_api("rt_k")),
        ("independent special API stk_auction_o", required_scope_for_api("stk_auction_o")),
        ("Kaipanla morning_bidding", "market:kaipanla:read"),
        ("MiniQMT", "market:miniqmt:read"),
        ("Admin", "admin:sync"),
    ]

    print(f"\nTushare catalog: total={len(rows)} points={len(point_rows)} independent={len(independent_rows)}")
    print("\nPermission matrix:")
    print(f"{'resource':42} {'general':>9} {'special':>9}  required_scope")
    for label, required in samples:
        general_ok = scope_allowed(required, GENERAL_SCOPES)
        special_ok = scope_allowed(required, SPECIAL_SCOPES)
        print(f"{label:42} {str(general_ok):>9} {str(special_ok):>9}  {required}")

    assert len(point_rows) + len(independent_rows) == len(rows)
    assert {row["api_name"] for row in independent_rows} == set(INDEPENDENT_PERMISSION_APIS)
    assert scope_allowed(required_scope_for_api("stock_basic"), GENERAL_SCOPES)
    assert not scope_allowed(required_scope_for_api("etf_mins"), GENERAL_SCOPES)
    assert not scope_allowed(required_scope_for_api("rt_k"), GENERAL_SCOPES)
    assert not scope_allowed("market:kaipanla:read", GENERAL_SCOPES)
    assert scope_allowed(required_scope_for_api("stock_basic"), SPECIAL_SCOPES)
    assert scope_allowed(required_scope_for_api("etf_mins"), SPECIAL_SCOPES)
    assert scope_allowed(required_scope_for_api("rt_k"), SPECIAL_SCOPES)
    assert scope_allowed(required_scope_for_api("stk_auction_o"), SPECIAL_SCOPES)
    assert scope_allowed("market:kaipanla:read", SPECIAL_SCOPES)
    assert not scope_allowed("market:miniqmt:read", SPECIAL_SCOPES)
    assert not scope_allowed("admin:sync", SPECIAL_SCOPES)

    print("\nPASS: six public plans and two permission tiers are correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
