# -*- coding: utf-8 -*-
"""Safely migrate the Kaipanla snapshot table to the v2 three-snapshot-compatible schema.

The application also performs this migration idempotently from ``init_db``.
This command exists for controlled production rollout: it validates the same
migration against a temporary SQLite copy, creates an online backup, applies
one transaction, and emits before/after evidence.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from services.kaipanla_snapshot_repository import create_kaipanla_snapshot_tables

_TABLE = "kaipanla_bidding_snapshots"
_REQUIRED_INDEX = "ux_kaipanla_snapshot_trade_type_hash"
_LEGACY_INDEX = "ux_kaipanla_snapshot_trade_hash"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def inspect_database(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在: {path}")
    conn = _connect(path)
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)
        ).fetchone() is not None
        if not table_exists:
            return {
                "db_path": str(path),
                "table_exists": False,
                "record_count": 0,
                "columns": [],
                "indexes": [],
                "snapshot_type_counts": {},
            }
        columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({_TABLE})")]
        indexes = [str(row[1]) for row in conn.execute(f"PRAGMA index_list({_TABLE})")]
        record_count = int(conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0])
        type_counts: dict[str, int] = {}
        if "snapshot_type" in columns:
            rows = conn.execute(
                f"SELECT snapshot_type,COUNT(*) AS cnt FROM {_TABLE} GROUP BY snapshot_type"
            ).fetchall()
            type_counts = {str(row[0]): int(row[1]) for row in rows}
        return {
            "db_path": str(path),
            "table_exists": True,
            "record_count": record_count,
            "columns": sorted(columns),
            "indexes": sorted(indexes),
            "snapshot_type_counts": type_counts,
        }
    finally:
        conn.close()


def _online_backup(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(f"备份文件已存在，拒绝覆盖: {destination_path}")
    source = _connect(source_path)
    destination = _connect(destination_path)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()


def _apply_schema(db_path: Path) -> dict[str, Any]:
    before = inspect_database(db_path)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        create_kaipanla_snapshot_tables(conn.cursor())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    after = inspect_database(db_path)
    if before["record_count"] != after["record_count"]:
        raise RuntimeError(
            f"迁移前后记录数不一致: {before['record_count']} -> {after['record_count']}"
        )
    if "snapshot_type" not in after["columns"]:
        raise RuntimeError("迁移后缺少 snapshot_type 列")
    if _REQUIRED_INDEX not in after["indexes"] or _LEGACY_INDEX in after["indexes"]:
        raise RuntimeError("迁移后快照唯一索引不符合三时点快照要求")
    invalid = set(after["snapshot_type_counts"]) - {"auction", "post_open", "close"}
    if invalid:
        raise RuntimeError(f"迁移后发现非法 snapshot_type: {sorted(invalid)}")
    return after


def _validate_on_temporary_copy(source_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="kaipanla-dual-snapshot-") as temp_dir:
        copy_path = Path(temp_dir) / "validation.db"
        _online_backup(source_path, copy_path)
        before = inspect_database(copy_path)
        first = _apply_schema(copy_path)
        second = _apply_schema(copy_path)
        if first != second:
            raise RuntimeError("临时数据库重复迁移结果不一致，幂等校验失败")
        return {"before": before, "after": first, "idempotent": True}


def migrate_database(
    db_path: str | Path,
    *,
    backup_path: str | Path | None = None,
    validate_copy: bool = True,
) -> dict[str, Any]:
    path = Path(db_path).expanduser().resolve()
    before = inspect_database(path)
    validation = _validate_on_temporary_copy(path) if validate_copy else None
    if backup_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_name(f"{path.name}.before_kaipanla_dual_snapshot_{stamp}.bak")
    else:
        backup = Path(backup_path).expanduser().resolve()
    _online_backup(path, backup)
    after = _apply_schema(path)
    return {
        "ok": True,
        "db_path": str(path),
        "backup_path": str(backup),
        "validation_copy": validation,
        "before": before,
        "after": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="安全迁移开盘啦v2三时点兼容表结构")
    parser.add_argument("--db", default=config.DB_FILE, help="SQLite数据库路径")
    parser.add_argument("--backup", help="备份文件路径；默认自动生成且绝不覆盖")
    parser.add_argument("--check-only", action="store_true", help="仅检查，不修改数据库")
    parser.add_argument("--skip-copy-validation", action="store_true", help="跳过临时副本预演（不推荐）")
    parser.add_argument("--report", help="可选JSON报告输出路径")
    args = parser.parse_args()
    report = (
        inspect_database(args.db)
        if args.check_only
        else migrate_database(
            args.db,
            backup_path=args.backup,
            validate_copy=not args.skip_copy_validation,
        )
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
