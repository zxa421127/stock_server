from __future__ import annotations

import sqlite3

from services.admin_client_certificate import (
    count_active_certificates,
    create_admin_client_certificate_tables,
    get_certificate_by_fingerprint,
    list_certificates,
    normalize_fingerprint,
    register_certificate,
    revoke_certificate,
    touch_certificate_use,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_admin_client_certificate_tables(conn.cursor())
    conn.commit()
    return conn


def test_register_lookup_touch_and_revoke_certificate():
    conn = _conn()
    fingerprint = "AA:" * 31 + "AA"
    row = register_certificate(
        admin_username="admin",
        device_name="main-pc",
        serial_number="01AB",
        fingerprint_sha256=fingerprint,
        subject_dn="CN=admin-main-pc",
        not_before="2026-01-01T00:00:00Z",
        not_after="2027-01-01T00:00:00Z",
        conn=conn,
    )
    assert row["fingerprint_sha256"] == "AA" * 32
    assert count_active_certificates(conn=conn) == 1
    found = get_certificate_by_fingerprint(fingerprint, conn=conn)
    assert found["device_name"] == "main-pc"

    touch_certificate_use(found["id"], ip_address="203.0.113.5", conn=conn)
    touched = get_certificate_by_fingerprint(fingerprint, conn=conn)
    assert touched["last_used_ip"] == "203.0.113.5"
    assert touched["last_used_at"]

    assert revoke_certificate(fingerprint=fingerprint, reason="lost", conn=conn)
    revoked = get_certificate_by_fingerprint(fingerprint, conn=conn)
    assert revoked["status"] == "revoked"
    assert revoked["revoked_reason"] == "lost"
    assert count_active_certificates(conn=conn) == 0
    assert len(list_certificates(conn=conn)) == 1


def test_fingerprint_normalization_rejects_invalid_values():
    assert normalize_fingerprint("ab:" * 31 + "ab") == "AB" * 32
    assert normalize_fingerprint("not-a-fingerprint") == ""
