# -*- coding: utf-8 -*-
"""Replace legacy public plans with the six-plan two-tier catalog.

The migration is idempotent and preserves existing users and subscription
validity periods.  Existing built-in subscriptions/orders are mapped before
legacy plan rows are deleted:

- history/developer_points -> general
- realtime/developer_full -> special

Only the known built-in public plan rows are removed.  Custom plans are left
untouched.  The internal administrator plan is retained.
"""
from __future__ import annotations

import json
from datetime import datetime

from db_utils import get_conn, init_db, upsert_plan_record
from services.plan_catalog import DEFAULT_PLANS, LEGACY_PUBLIC_PLAN_MIGRATION

NEW_PUBLIC_PLAN_CODES = {
    plan["plan_code"] for plan in DEFAULT_PLANS if plan.get("public")
}


def _plan_map() -> dict[str, dict]:
    return {plan["plan_code"]: plan for plan in DEFAULT_PLANS}


def main() -> None:
    init_db()
    plans = _plan_map()

    # Ensure all six public plans and the internal admin plan have the exact
    # current names, prices, quotas, durations and scopes.
    for plan in DEFAULT_PLANS:
        upsert_plan_record(plan, update_existing=True)

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if conn.in_transaction:
        conn.commit()
    cursor.execute("BEGIN IMMEDIATE")
    try:
        migrated_subscriptions = 0
        migrated_orders = 0

        for old_code, new_code in LEGACY_PUBLIC_PLAN_MIGRATION.items():
            target = plans[new_code]

            cursor.execute(
                "UPDATE subscriptions SET plan_code=?,plan_type=?,updated_at=? WHERE plan_code=?",
                (new_code, target["plan_type"], now, old_code),
            )
            migrated_subscriptions += max(int(cursor.rowcount or 0), 0)

            cursor.execute(
                "UPDATE manual_orders SET plan_code=?,plan_type=?,duration_type=? WHERE plan_code=?",
                (new_code, target["plan_type"], target["duration_type"], old_code),
            )
            migrated_orders += max(int(cursor.rowcount or 0), 0)

            # Preserve previous-plan audit references but translate the code so
            # the后台 no longer displays removed plan codes.
            cursor.execute(
                "UPDATE manual_orders SET previous_plan_code=? WHERE previous_plan_code=?",
                (new_code, old_code),
            )

        legacy_codes = sorted(LEGACY_PUBLIC_PLAN_MIGRATION)
        placeholders = ",".join("?" for _ in legacy_codes)
        cursor.execute(
            f"DELETE FROM plans WHERE plan_code IN ({placeholders})",
            legacy_codes,
        )
        deleted_legacy_plans = max(int(cursor.rowcount or 0), 0)

        # Keep stored API-document scopes aligned with the runtime permission
        # resolver introduced by the previous patch.
        cursor.execute(
            "UPDATE api_doc_endpoints SET scope=?,updated_at=? WHERE path LIKE ?",
            ("tushare:independent:realtime:read", now, "%/market/tushare/rt_k%"),
        )
        cursor.execute(
            "UPDATE api_doc_endpoints SET scope=?,updated_at=? "
            "WHERE path LIKE ? OR path LIKE ?",
            (
                "tushare:points15000:read",
                now,
                "%/market/tushare/stock_basic%",
                "%/market/tushare/trade_cal%",
            ),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    active_rows = cursor.execute(
        "SELECT plan_code,plan_name,plan_type,duration_days,sale_price_cent,status "
        "FROM plans WHERE status='active' ORDER BY "
        "CASE plan_type WHEN 'general' THEN 0 WHEN 'special' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END, "
        "duration_days,id"
    ).fetchall()

    public_rows = [row for row in active_rows if row["plan_code"] in NEW_PUBLIC_PLAN_CODES]
    remaining_legacy = cursor.execute(
        f"SELECT plan_code FROM plans WHERE plan_code IN ({placeholders})",
        legacy_codes,
    ).fetchall()

    print("Two-tier public plan catalog installed:")
    for row in public_rows:
        print(
            f"  {row['plan_code']:<18} | {row['plan_name']} | "
            f"price={row['sale_price_cent'] / 100:.2f} | days={row['duration_days']}"
        )
    print(f"Migrated subscriptions: {migrated_subscriptions}")
    print(f"Migrated manual orders: {migrated_orders}")
    print(f"Deleted legacy public plan rows: {deleted_legacy_plans}")
    print(f"Remaining legacy plan rows: {len(remaining_legacy)}")

    if len(public_rows) != 6:
        raise SystemExit(f"Expected 6 active public plans, found {len(public_rows)}")
    if remaining_legacy:
        raise SystemExit("Legacy public plan rows still exist")


if __name__ == "__main__":
    main()
