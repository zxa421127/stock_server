# -*- coding: utf-8 -*-
"""Immutable, compressed SQLite repository for Kaipanla bidding snapshots."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import pandas as pd

from db_utils import get_conn
from integrations.market_data.kaipanla.schema import SCHEMA_VERSION, SNAPSHOT_TYPES

ConnectionFactory = Callable[[], sqlite3.Connection]


def validate_snapshot_type(value: Any, default: str = "auction") -> str:
    """Normalize and validate the public snapshot type enum."""
    text = str(value or default).strip().lower()
    if text not in SNAPSHOT_TYPES:
        raise ValueError("snapshot_type 只允许 auction、post_open 或 close")
    return text


def create_kaipanla_snapshot_tables(cursor: sqlite3.Cursor) -> None:
    """Create or idempotently migrate the immutable snapshot tables."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kaipanla_bidding_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            trade_date TEXT NOT NULL,
            snapshot_type TEXT NOT NULL DEFAULT 'auction',
            snapshot_time TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            source_api TEXT NOT NULL,
            source_params_json TEXT NOT NULL,
            raw_payload_gzip BLOB NOT NULL,
            normalized_payload_gzip BLOB NOT NULL,
            record_count INTEGER NOT NULL,
            payload_hash TEXT NOT NULL,
            data_quality TEXT NOT NULL,
            schema_version TEXT NOT NULL DEFAULT 'kaipanla_bidding.v2',
            created_at TEXT NOT NULL
        )
        """
    )
    columns = {
        row[1]
        for row in cursor.execute(
            "PRAGMA table_info(kaipanla_bidding_snapshots)"
        ).fetchall()
    }
    if "schema_version" not in columns:
        cursor.execute(
            "ALTER TABLE kaipanla_bidding_snapshots "
            "ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'kaipanla_bidding.v1'"
        )
    if "snapshot_type" not in columns:
        cursor.execute(
            "ALTER TABLE kaipanla_bidding_snapshots "
            "ADD COLUMN snapshot_type TEXT NOT NULL DEFAULT 'auction'"
        )
    cursor.execute(
        "UPDATE kaipanla_bidding_snapshots SET snapshot_type='auction' "
        "WHERE snapshot_type IS NULL OR TRIM(snapshot_type)=''"
    )

    # The legacy uniqueness omitted snapshot_type and would make official
    # captures overwrite/deduplicate each other when their payloads match.
    cursor.execute("DROP INDEX IF EXISTS ux_kaipanla_snapshot_trade_hash")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_kaipanla_snapshot_trade_type_hash "
        "ON kaipanla_bidding_snapshots(trade_date,snapshot_type,payload_hash)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_kaipanla_snapshot_trade_type_time "
        "ON kaipanla_bidding_snapshots(trade_date DESC,snapshot_type,snapshot_time ASC)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kaipanla_snapshot_leases (
            lease_name TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            lease_until REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _json_default(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def _compress_json(value: Any) -> bytes:
    return gzip.compress(_json_bytes(value), compresslevel=6)


def _decompress_json(value: bytes) -> Any:
    return json.loads(gzip.decompress(value).decode("utf-8"))


def _stable_payload_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    transient = {"snapshot_id", "snapshot_time", "snapshot_type"}
    return [
        {key: value for key, value in dict(row).items() if key not in transient}
        for row in rows
    ]


def _snapshot_id(
    trade_date: str,
    snapshot_time: str,
    snapshot_type: str,
    payload_hash: str,
) -> str:
    compact = re.sub(r"\D", "", snapshot_time)
    clock = compact[8:14] if len(compact) >= 14 else "000000"
    return f"{trade_date}_{clock}_{snapshot_type}_{payload_hash[:12]}"


@dataclass(slots=True)
class KaipanlaSnapshot:
    snapshot_id: str
    trade_date: str
    snapshot_type: str
    snapshot_time: str
    source_provider: str
    source_api: str
    source_params: dict[str, Any]
    raw_payload: Any
    normalized_data: list[dict[str, Any]]
    record_count: int
    payload_hash: str
    data_quality: str
    schema_version: str
    created_at: str


@dataclass(slots=True)
class SnapshotSaveResult:
    snapshot: KaipanlaSnapshot
    created: bool


class KaipanlaSnapshotRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory | None = None,
        *,
        ensure_schema: bool = True,
    ) -> None:
        self._connection_factory = connection_factory or get_conn
        if ensure_schema:
            self.ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = self._connection_factory()
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        conn = self._conn()
        try:
            create_kaipanla_snapshot_tables(conn.cursor())
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def _validate_trade_date(value: str) -> str:
        text = str(value or "").strip()
        try:
            datetime.strptime(text, "%Y%m%d")
        except ValueError as exc:
            raise ValueError("trade_date 必须为 YYYYMMDD") from exc
        return text

    def _row_to_snapshot(self, row: sqlite3.Row | None) -> KaipanlaSnapshot | None:
        if row is None:
            return None
        snapshot_type = validate_snapshot_type(row["snapshot_type"])
        normalized = _decompress_json(row["normalized_payload_gzip"])
        for item in normalized:
            item["snapshot_id"] = str(row["snapshot_id"])
            item["trade_date"] = str(row["trade_date"])
            item["snapshot_type"] = snapshot_type
            item["snapshot_time"] = str(row["snapshot_time"])
            item["schema_version"] = str(
                row["schema_version"]
                or item.get("schema_version")
                or SCHEMA_VERSION
            )
        return KaipanlaSnapshot(
            snapshot_id=str(row["snapshot_id"]),
            trade_date=str(row["trade_date"]),
            snapshot_type=snapshot_type,
            snapshot_time=str(row["snapshot_time"]),
            source_provider=str(row["source_provider"]),
            source_api=str(row["source_api"]),
            source_params=json.loads(row["source_params_json"] or "{}"),
            raw_payload=_decompress_json(row["raw_payload_gzip"]),
            normalized_data=normalized,
            record_count=int(row["record_count"] or 0),
            payload_hash=str(row["payload_hash"]),
            data_quality=str(row["data_quality"]),
            schema_version=str(row["schema_version"] or SCHEMA_VERSION),
            created_at=str(row["created_at"]),
        )

    def save_snapshot(
        self,
        *,
        trade_date: str,
        snapshot_time: str,
        source_params: dict[str, Any],
        raw_payload: Any,
        normalized_data: list[dict[str, Any]],
        snapshot_type: str = "auction",
        data_quality: str = "complete",
        source_provider: str = "kaipanla",
        source_api: str = "morning_bidding",
        schema_version: str = SCHEMA_VERSION,
    ) -> SnapshotSaveResult:
        trade_date = self._validate_trade_date(trade_date)
        snapshot_type = validate_snapshot_type(snapshot_type)
        if not snapshot_time:
            raise ValueError("snapshot_time 不能为空")
        stable_rows = _stable_payload_rows(normalized_data)
        payload_hash = hashlib.sha256(
            _json_bytes(
                {
                    "snapshot_type": snapshot_type,
                    "raw_payload": raw_payload,
                    "normalized_data": stable_rows,
                }
            )
        ).hexdigest()
        snapshot_id = _snapshot_id(
            trade_date, snapshot_time, snapshot_type, payload_hash
        )
        rows = [dict(row) for row in normalized_data]
        for row in rows:
            row.update(
                {
                    "trade_date": trade_date,
                    "snapshot_type": snapshot_type,
                    "snapshot_time": snapshot_time,
                    "snapshot_id": snapshot_id,
                    "schema_version": schema_version,
                }
            )
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            # One immutable official snapshot per date/type. This blocks a later
            # retry with changed upstream data from replacing the first capture.
            existing = conn.execute(
                "SELECT * FROM kaipanla_bidding_snapshots "
                "WHERE trade_date=? AND snapshot_type=? "
                "ORDER BY snapshot_time ASC,created_at ASC LIMIT 1",
                (trade_date, snapshot_type),
            ).fetchone()
            if existing is not None:
                conn.commit()
                return SnapshotSaveResult(self._row_to_snapshot(existing), False)
            conn.execute(
                """
                INSERT INTO kaipanla_bidding_snapshots(
                    snapshot_id,trade_date,snapshot_type,snapshot_time,
                    source_provider,source_api,source_params_json,
                    raw_payload_gzip,normalized_payload_gzip,record_count,
                    payload_hash,data_quality,schema_version,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    snapshot_id,
                    trade_date,
                    snapshot_type,
                    snapshot_time,
                    source_provider,
                    source_api,
                    _json_bytes(source_params).decode("utf-8"),
                    _compress_json(raw_payload),
                    _compress_json(rows),
                    len(rows),
                    payload_hash,
                    data_quality,
                    schema_version,
                    created_at,
                ),
            )
            conn.commit()
            saved = self.get_by_id(snapshot_id)
            if saved is None:
                raise RuntimeError("快照写入后无法读取")
            return SnapshotSaveResult(saved, True)
        except sqlite3.IntegrityError:
            conn.rollback()
            row = self._conn().execute(
                "SELECT * FROM kaipanla_bidding_snapshots "
                "WHERE trade_date=? AND snapshot_type=? "
                "ORDER BY snapshot_time ASC,created_at ASC LIMIT 1",
                (trade_date, snapshot_type),
            ).fetchone()
            existing = self._row_to_snapshot(row)
            if existing is None:
                raise
            return SnapshotSaveResult(existing, False)
        except Exception:
            conn.rollback()
            raise

    def get_by_id(self, snapshot_id: str) -> KaipanlaSnapshot | None:
        row = self._conn().execute(
            "SELECT * FROM kaipanla_bidding_snapshots WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        return self._row_to_snapshot(row)

    def get_snapshot(
        self, trade_date: str, snapshot_type: str = "auction"
    ) -> KaipanlaSnapshot | None:
        trade_date = self._validate_trade_date(trade_date)
        snapshot_type = validate_snapshot_type(snapshot_type)
        row = self._conn().execute(
            "SELECT * FROM kaipanla_bidding_snapshots "
            "WHERE trade_date=? AND snapshot_type=? "
            "ORDER BY snapshot_time ASC,created_at ASC LIMIT 1",
            (trade_date, snapshot_type),
        ).fetchone()
        return self._row_to_snapshot(row)

    def get_latest_snapshot(
        self,
        on_or_before: str | None = None,
        snapshot_type: str = "auction",
    ) -> KaipanlaSnapshot | None:
        snapshot_type = validate_snapshot_type(snapshot_type)
        conn = self._conn()
        if on_or_before:
            bound = self._validate_trade_date(on_or_before)
            row = conn.execute(
                "SELECT * FROM kaipanla_bidding_snapshots "
                "WHERE trade_date<=? AND snapshot_type=? "
                "ORDER BY trade_date DESC,snapshot_time ASC,created_at ASC LIMIT 1",
                (bound, snapshot_type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM kaipanla_bidding_snapshots "
                "WHERE snapshot_type=? "
                "ORDER BY trade_date DESC,snapshot_time ASC,created_at ASC LIMIT 1",
                (snapshot_type,),
            ).fetchone()
        return self._row_to_snapshot(row)

    def has_snapshot(self, trade_date: str, snapshot_type: str = "auction") -> bool:
        return self.get_snapshot(trade_date, snapshot_type) is not None

    def acquire_lease(
        self,
        lease_name: str,
        owner_id: str,
        ttl_seconds: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        epoch = now.timestamp()
        until = epoch + max(int(ttl_seconds), 1)
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT owner_id,lease_until FROM kaipanla_snapshot_leases "
                "WHERE lease_name=?",
                (lease_name,),
            ).fetchone()
            if (
                row is not None
                and str(row["owner_id"]) != owner_id
                and float(row["lease_until"]) > epoch
            ):
                conn.rollback()
                return False
            conn.execute(
                """
                INSERT INTO kaipanla_snapshot_leases(
                    lease_name,owner_id,lease_until,updated_at
                ) VALUES(?,?,?,?)
                ON CONFLICT(lease_name) DO UPDATE SET
                    owner_id=excluded.owner_id,
                    lease_until=excluded.lease_until,
                    updated_at=excluded.updated_at
                """,
                (
                    lease_name,
                    owner_id,
                    until,
                    now.isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def release_lease(self, lease_name: str, owner_id: str) -> None:
        conn = self._conn()
        conn.execute(
            "DELETE FROM kaipanla_snapshot_leases "
            "WHERE lease_name=? AND owner_id=?",
            (lease_name, owner_id),
        )
        conn.commit()

    def prune_before(self, trade_date: str) -> int:
        trade_date = self._validate_trade_date(trade_date)
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM kaipanla_bidding_snapshots WHERE trade_date<?",
            (trade_date,),
        )
        conn.commit()
        return max(int(cur.rowcount or 0), 0)

    def iter_snapshots(self) -> list[KaipanlaSnapshot]:
        rows = self._conn().execute(
            "SELECT * FROM kaipanla_bidding_snapshots "
            "ORDER BY trade_date,snapshot_type,snapshot_time"
        ).fetchall()
        return [snapshot for row in rows if (snapshot := self._row_to_snapshot(row))]

    def update_normalized_payload(
        self,
        snapshot_id: str,
        normalized_data: list[dict[str, Any]],
        *,
        schema_version: str = SCHEMA_VERSION,
    ) -> None:
        rows = [dict(row) for row in normalized_data]
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute(
                "SELECT trade_date,snapshot_type,snapshot_time "
                "FROM kaipanla_bidding_snapshots WHERE snapshot_id=?",
                (snapshot_id,),
            ).fetchone()
            if current is None:
                raise KeyError(snapshot_id)
            for row in rows:
                row.update(
                    {
                        "snapshot_id": snapshot_id,
                        "trade_date": current["trade_date"],
                        "snapshot_type": current["snapshot_type"],
                        "snapshot_time": current["snapshot_time"],
                        "schema_version": schema_version,
                    }
                )
            conn.execute(
                "UPDATE kaipanla_bidding_snapshots SET "
                "normalized_payload_gzip=?,record_count=?,schema_version=? "
                "WHERE snapshot_id=?",
                (_compress_json(rows), len(rows), schema_version, snapshot_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
