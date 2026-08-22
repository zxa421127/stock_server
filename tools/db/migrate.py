# -*- coding: utf-8 -*-
"""Apply all database migrations before starting production web/worker services."""
from __future__ import annotations

from db_utils import CURRENT_SCHEMA_VERSION, close_thread_connection, init_db


def main() -> int:
    init_db()
    close_thread_connection()
    print(f"数据库迁移完成，schema_version={CURRENT_SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
