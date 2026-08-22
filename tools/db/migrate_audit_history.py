# -*- coding: utf-8 -*-
"""Initialize and verify audit history schemas before production restart.

Run from the project root:
    python -m tools.db.migrate_audit_history
"""
from __future__ import annotations

import config
from db_utils import get_conn, init_db
from services.audit_schema import init_spool_schema

_TABLES = ("operation_audit_logs", "api_access_logs", "audit_maintenance_state")


def _schema_summary() -> dict[str, int]:
    conn = get_conn()
    result: dict[str, int] = {}
    for table in _TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            raise RuntimeError(f"缺少审计表：{table}")
        result[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    return result


def main() -> int:
    init_db()
    init_spool_schema(config.AUDIT_SPOOL_DB_FILE, config.AUDIT_SPOOL_SYNCHRONOUS)
    summary = _schema_summary()
    print("审计历史数据库迁移完成。")
    print("主数据库:", config.DB_FILE)
    print("持久化缓冲:", config.AUDIT_SPOOL_DB_FILE)
    for table, count in summary.items():
        print(f"  {table}: {count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
