# -*- coding: utf-8 -*-
"""Revoke legacy plaintext ``api_tokens`` credentials.

Historic versions copied plaintext credentials into the new membership tables.
That behavior is intentionally removed: legacy values are only revoked and are
never promoted to ``api_keys``.
"""
from __future__ import annotations

import argparse
import sqlite3

from db_utils import get_conn, init_db

_REVOKED_STATUSES = {
    "disabled", "inactive", "revoked", "expired", "cancelled",
    "已禁用", "禁用", "已撤销", "撤销", "已过期", "过期",
}


def _table_exists(conn: sqlite3.Connection) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='api_tokens'"
    ).fetchone())


def _status_column_exists(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn):
        return False
    return "status" in {row[1] for row in conn.execute("PRAGMA table_info(api_tokens)").fetchall()}


def _active_ids(conn: sqlite3.Connection) -> list[int]:
    if not _table_exists(conn):
        return []
    has_status = _status_column_exists(conn)
    select = "SELECT id,token" + (",status" if has_status else "") + " FROM api_tokens"
    active: list[int] = []
    for row in conn.execute(select).fetchall():
        token = str(row[1] or "").strip()
        status = str(row[2] or "").strip().lower() if has_status else ""
        if token and status not in _REVOKED_STATUSES:
            active.append(int(row[0]))
    return active


def count_active_legacy_tokens(conn: sqlite3.Connection) -> int:
    return len(_active_ids(conn))


def revoke_legacy_tokens(conn: sqlite3.Connection, *, dry_run: bool = False) -> int:
    ids = _active_ids(conn)
    if not ids or dry_run:
        return len(ids)
    if not _status_column_exists(conn):
        conn.execute("ALTER TABLE api_tokens ADD COLUMN status TEXT")
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE api_tokens SET status='revoked' WHERE id IN ({placeholders})",
        tuple(ids),
    )
    conn.commit()
    return len(ids)


def migrate(*, dry_run: bool = False) -> int:
    init_db()
    conn = get_conn()
    count = revoke_legacy_tokens(conn, dry_run=dry_run)
    action = "将吊销" if dry_run else "已吊销"
    print(f"{action} {count} 个旧 api_tokens 明文凭证；不会创建用户、套餐或 api_keys。")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="吊销旧api_tokens明文凭证，禁止迁移为新Token")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不修改数据库")
    parser.add_argument("--confirm", default="", help="实际执行时必须为 REVOKE-LEGACY")
    args = parser.parse_args()
    if not args.dry_run and args.confirm != "REVOKE-LEGACY":
        parser.error("实际执行必须传入 --confirm REVOKE-LEGACY")
    migrate(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
