from __future__ import annotations

import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.serialization import pkcs12

from services.admin_client_certificate import create_admin_client_certificate_tables, get_certificate_by_fingerprint
from tools.security.admin_client_certificate import initialize_ca, issue_certificate


def test_initialize_ca_and_issue_registered_pkcs12(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_admin_client_certificate_tables(conn.cursor())
    conn.commit()

    ca_dir = tmp_path / "ca"
    ca = initialize_ca(ca_dir, password="ca-password-very-strong", common_name="Test Admin CA", valid_days=3650)
    assert Path(ca["certificate_path"]).is_file()
    assert Path(ca["private_key_path"]).is_file()

    issued = issue_certificate(
        ca_dir=ca_dir,
        ca_password="ca-password-very-strong",
        output_dir=tmp_path / "clients",
        pfx_password="pfx-password-very-strong",
        admin_username="admin",
        device_name="main-pc",
        valid_days=365,
        conn=conn,
    )
    pfx_path = Path(issued["pfx_path"])
    assert pfx_path.is_file()
    key, certificate, chain = pkcs12.load_key_and_certificates(
        pfx_path.read_bytes(), b"pfx-password-very-strong"
    )
    assert key is not None
    assert certificate is not None
    assert chain
    registered = get_certificate_by_fingerprint(issued["fingerprint_sha256"], conn=conn)
    assert registered["device_name"] == "main-pc"
    assert registered["status"] == "active"


def test_forwarded_pem_header_produces_sha256_details(tmp_path: Path):
    from urllib.parse import quote
    from flask import Flask
    from services import admin_auth

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_admin_client_certificate_tables(conn.cursor())
    conn.commit()
    ca_dir = tmp_path / "ca"
    initialize_ca(ca_dir, password="ca-password-very-strong", common_name="Test Admin CA", valid_days=3650)
    issued = issue_certificate(
        ca_dir=ca_dir,
        ca_password="ca-password-very-strong",
        output_dir=tmp_path / "clients",
        pfx_password="pfx-password-very-strong",
        admin_username="admin",
        device_name="main-pc",
        valid_days=365,
        conn=conn,
    )
    pem = Path(issued["certificate_path"]).read_text(encoding="utf-8")
    app = Flask(__name__)
    with app.test_request_context(
        "/admin/login",
        headers={"X-Admin-Client-Cert": quote(pem, safe="")},
    ):
        details = admin_auth._forwarded_certificate_details()
    assert details is not None
    assert details["fingerprint_sha256"] == issued["fingerprint_sha256"]
    assert details["serial_number"] == issued["serial_number"]
