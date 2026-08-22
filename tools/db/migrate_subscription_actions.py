# -*- coding: utf-8 -*-
"""Initialize and verify the explicit subscription-action schema.

Usage:
    python -m tools.db.migrate_subscription_actions

The application also runs the same safe column/status migration during startup.
This command is provided so administrators can verify the database before
restarting the production service.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from db_utils import DB_FILE, get_conn, init_db, refresh_subscription_states


def main() -> int:
    print("数据库:", DB_FILE)
    init_db()
    refresh_subscription_states()
    conn = get_conn()
    cursor = conn.cursor()

    sub_cols = [row[1] for row in cursor.execute("PRAGMA table_info(subscriptions)").fetchall()]
    order_cols = [row[1] for row in cursor.execute("PRAGMA table_info(manual_orders)").fetchall()]
    required_sub = {
        "operation_type", "previous_subscription_id", "extra_days", "ended_at", "ended_reason"
    }
    required_order = {
        "operation_type", "subscription_id", "previous_subscription_id", "previous_plan_code",
        "effective_time", "extra_days", "operator_name"
    }
    missing_sub = sorted(required_sub - set(sub_cols))
    missing_order = sorted(required_order - set(order_cols))
    if missing_sub or missing_order:
        print("迁移失败，缺少字段:")
        print("subscriptions:", missing_sub)
        print("manual_orders:", missing_order)
        return 1

    counts = dict(cursor.execute(
        "SELECT status,COUNT(*) FROM subscriptions GROUP BY status ORDER BY status"
    ).fetchall())
    print("订阅状态统计:", counts)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overlaps = cursor.execute(
        """
        SELECT user_id,COUNT(*) AS cnt,GROUP_CONCAT(id) AS ids
        FROM subscriptions
        WHERE status='active' AND start_time<=? AND expire_time>=?
        GROUP BY user_id HAVING COUNT(*)>1
        """,
        (now, now),
    ).fetchall()
    if overlaps:
        print("警告：以下用户存在多条同时生效订阅，请人工核对：")
        for row in overlaps:
            print(f"  user_id={row['user_id']} count={row['cnt']} subscription_ids={row['ids']}")
    else:
        print("检查通过：没有用户存在多条同时生效订阅。")

    print("订阅操作字段迁移完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
