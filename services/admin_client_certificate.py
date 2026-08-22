# -*- coding: utf-8 -*-
"""SQLite registry for administrator mutual-TLS client certificates."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

_HEX64 = re.compile(r"^[0-9A-F]{64}$")


def _now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_fingerprint(value: str | None) -> str:
    normalized = re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()
    return normalized if _HEX64.fullmatch(normalized) else ""


def normalize_serial(value: str | None) -> str:
    normalized = re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper().lstrip("0")
    return normalized or ("0" if str(value or "").strip() else "")


def create_admin_client_certificate_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_client_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT NOT NULL,
            device_name TEXT NOT NULL,
            serial_number TEXT NOT NULL UNIQUE,
            fingerprint_sha256 TEXT NOT NULL UNIQUE,
            subject_dn TEXT NOT NULL DEFAULT '',
            not_before TEXT NOT NULL,
            not_after TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            revoked_at TEXT,
            revoked_reason TEXT NOT NULL DEFAULT '',
            last_used_at TEXT,
            last_used_ip TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_client_cert_user_status "
        "ON admin_client_certificates(admin_username, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_client_cert_expiry "
        "ON admin_client_certificates(not_after, status)"
    )


def _connection(conn=None):
    if conn is not None:
        return conn
    from db_utils import get_conn
    return get_conn()


def _dict(row):
    return dict(row) if row is not None else None


def register_certificate(
    *,
    admin_username: str,
    device_name: str,
    serial_number: str,
    fingerprint_sha256: str,
    subject_dn: str,
    not_before: str,
    not_after: str,
    metadata: dict[str, Any] | None = None,
    conn=None,
) -> dict[str, Any]:
    fingerprint = normalize_fingerprint(fingerprint_sha256)
    serial = normalize_serial(serial_number)
    if not fingerprint:
        raise ValueError("无效的SHA-256证书指纹")
    if not serial:
        raise ValueError("无效的证书序列号")
    admin = str(admin_username or "").strip()
    device = str(device_name or "").strip()
    if not admin or not device:
        raise ValueError("管理员账号和设备名称不能为空")
    database = _connection(conn)
    created_at = _now_text()
    database.execute(
        """
        INSERT INTO admin_client_certificates(
            admin_username, device_name, serial_number, fingerprint_sha256,
            subject_dn, not_before, not_after, status, created_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        ON CONFLICT(fingerprint_sha256) DO UPDATE SET
            admin_username=excluded.admin_username,
            device_name=excluded.device_name,
            serial_number=excluded.serial_number,
            subject_dn=excluded.subject_dn,
            not_before=excluded.not_before,
            not_after=excluded.not_after,
            status='active',
            revoked_at=NULL,
            revoked_reason='',
            metadata_json=excluded.metadata_json
        """,
        (
            admin,
            device,
            serial,
            fingerprint,
            str(subject_dn or ""),
            str(not_before or ""),
            str(not_after or ""),
            created_at,
            json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":")),
        ),
    )
    database.commit()
    return get_certificate_by_fingerprint(fingerprint, conn=database) or {}


def get_certificate_by_fingerprint(fingerprint: str | None, *, conn=None) -> dict[str, Any] | None:
    normalized = normalize_fingerprint(fingerprint)
    if not normalized:
        return None
    row = _connection(conn).execute(
        "SELECT * FROM admin_client_certificates WHERE fingerprint_sha256=? LIMIT 1",
        (normalized,),
    ).fetchone()
    return _dict(row)


def list_certificates(*, admin_username: str | None = None, conn=None) -> list[dict[str, Any]]:
    database = _connection(conn)
    if admin_username:
        rows = database.execute(
            "SELECT * FROM admin_client_certificates WHERE admin_username=? ORDER BY id DESC",
            (str(admin_username),),
        ).fetchall()
    else:
        rows = database.execute("SELECT * FROM admin_client_certificates ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def count_active_certificates(*, admin_username: str | None = None, conn=None) -> int:
    database = _connection(conn)
    now = _now_text()
    if admin_username:
        row = database.execute(
            """SELECT COUNT(*) AS count FROM admin_client_certificates
               WHERE admin_username=? AND status='active' AND not_before<=? AND not_after>?""",
            (str(admin_username), now, now),
        ).fetchone()
    else:
        row = database.execute(
            """SELECT COUNT(*) AS count FROM admin_client_certificates
               WHERE status='active' AND not_before<=? AND not_after>?""",
            (now, now),
        ).fetchone()
    return int(row["count"] if row else 0)


def revoke_certificate(
    *,
    fingerprint: str | None = None,
    serial_number: str | None = None,
    reason: str = "",
    conn=None,
) -> bool:
    database = _connection(conn)
    if fingerprint:
        field, value = "fingerprint_sha256", normalize_fingerprint(fingerprint)
    else:
        field, value = "serial_number", normalize_serial(serial_number)
    if not value:
        return False
    cursor = database.execute(
        f"""UPDATE admin_client_certificates
            SET status='revoked', revoked_at=?, revoked_reason=?
            WHERE {field}=? AND status!='revoked'""",
        (_now_text(), str(reason or "")[:500], value),
    )
    database.commit()
    return int(cursor.rowcount or 0) > 0


def touch_certificate_use(certificate_id: int, *, ip_address: str = "", conn=None) -> bool:
    database = _connection(conn)
    cursor = database.execute(
        "UPDATE admin_client_certificates SET last_used_at=?, last_used_ip=? WHERE id=?",
        (_now_text(), str(ip_address or "")[:128], int(certificate_id)),
    )
    database.commit()
    return int(cursor.rowcount or 0) > 0
