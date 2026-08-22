# -*- coding: utf-8 -*-
"""Upgrade existing plans for the provider architecture without changing prices."""
from __future__ import annotations

import json

from db_utils import get_conn, init_db
from services.plan_catalog import DEFAULT_PLANS


def main() -> None:
    init_db()
    conn = get_conn()
    cursor = conn.cursor()
    updated = 0
    defaults = {item["plan_code"]: item for item in DEFAULT_PLANS}

    cursor.execute("SELECT plan_code, plan_type, scopes, quota_per_minute FROM plans")
    for row in cursor.fetchall():
        plan_code = row["plan_code"]
        template = defaults.get(plan_code)
        try:
            current_scopes = json.loads(row["scopes"] or "[]")
        except Exception:
            current_scopes = []
        if not isinstance(current_scopes, list):
            current_scopes = []

        target_scopes = list(current_scopes)
        if template:
            for scope in template["scopes"]:
                if scope not in target_scopes:
                    target_scopes.append(scope)

        quota_per_minute = int(row["quota_per_minute"] or 0)
        if row["plan_type"] != "admin":
            quota_per_minute = max(quota_per_minute, 1000)

        cursor.execute(
            "UPDATE plans SET scopes=?, quota_per_minute=? WHERE plan_code=?",
            (json.dumps(target_scopes, ensure_ascii=False), quota_per_minute, plan_code),
        )
        updated += cursor.rowcount

    conn.commit()
    print(f"迁移完成：更新 {updated} 个套餐；价格、有效期和每日额度均未修改。")


if __name__ == "__main__":
    main()
