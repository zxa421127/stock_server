# -*- coding: utf-8 -*-
"""Delete old sampled usage detail rows while preserving daily aggregate counters."""
from __future__ import annotations

from datetime import datetime, timedelta

import config
from db_utils import get_conn, init_db


def main() -> None:
    init_db()
    cutoff = (datetime.now() - timedelta(days=config.USAGE_LOG_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usage_logs WHERE created_at < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
    print(f"usage_logs 清理完成：删除 {deleted} 条，保留最近 {config.USAGE_LOG_RETENTION_DAYS} 天明细；每日汇总未删除。")


if __name__ == "__main__":
    main()
