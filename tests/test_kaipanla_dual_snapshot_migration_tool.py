# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

from tools.db.migrate_kaipanla_dual_snapshot import inspect_database, migrate_database


def _legacy_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE kaipanla_bidding_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            trade_date TEXT NOT NULL,
            snapshot_time TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            source_api TEXT NOT NULL,
            source_params_json TEXT NOT NULL,
            raw_payload_gzip BLOB NOT NULL,
            normalized_payload_gzip BLOB NOT NULL,
            record_count INTEGER NOT NULL,
            payload_hash TEXT NOT NULL,
            data_quality TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX ux_kaipanla_snapshot_trade_hash "
        "ON kaipanla_bidding_snapshots(trade_date,payload_hash)"
    )
    conn.execute(
        "INSERT INTO kaipanla_bidding_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "20260722_092605_abcdef",
            "20260722",
            "2026-07-22 09:26:05",
            "kaipanla",
            "morning_bidding",
            "{}",
            b"raw",
            b"normalized",
            1,
            "hash1",
            "complete",
            "kaipanla_bidding.v2",
            "2026-07-22T01:26:06+00:00",
        ),
    )
    conn.commit()
    conn.close()


def test_migration_backs_up_backfills_type_and_is_idempotent(tmp_path):
    db = tmp_path / "prod.db"
    backup = tmp_path / "prod.before-dual-snapshot.db"
    _legacy_db(db)

    report = migrate_database(db, backup_path=backup, validate_copy=True)
    assert report["ok"] is True
    assert report["backup_path"] == str(backup)
    assert backup.exists()
    assert report["before"]["record_count"] == report["after"]["record_count"] == 1
    assert report["after"]["snapshot_type_counts"] == {"auction": 1}
    assert "snapshot_type" in report["after"]["columns"]
    assert "ux_kaipanla_snapshot_trade_hash" not in report["after"]["indexes"]
    assert "ux_kaipanla_snapshot_trade_type_hash" in report["after"]["indexes"]

    second = migrate_database(db, backup_path=tmp_path / "second.db", validate_copy=True)
    assert second["ok"] is True
    assert second["after"] == report["after"]


def test_check_only_does_not_mutate_legacy_database(tmp_path):
    db = tmp_path / "legacy.db"
    _legacy_db(db)
    before = inspect_database(db)
    assert "snapshot_type" not in before["columns"]
    assert inspect_database(db)["columns"] == before["columns"]
