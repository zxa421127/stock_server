from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from tools.release.build_production_package import build
from tools.security.scan_release_secrets import scan_zip


def _zip(path: Path, files: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_scanner_rejects_runtime_databases_virtualenv_and_private_keys(tmp_path):
    path = _zip(
        tmp_path / "bad.zip",
        {
            "nested/.venv/pyvenv.cfg": "home=x",
            "data/users.sqlite3": b"SQLite format 3\x00",
            "deploy/admin-client.key": "-----BEGIN PRIVATE KEY-----\nabc\n",
        },
    )
    findings = " ".join(scan_zip(path))
    assert ".venv" in findings
    assert "sqlite3" in findings
    assert "PRIVATE KEY" in findings or ".key" in findings


def test_scanner_rejects_new_security_secrets(tmp_path):
    path = _zip(
        tmp_path / "bad-secrets.zip",
        {"settings.env": "CONTACT_VERIFICATION_HMAC_SECRET=real-secret-value-1234567890\nSMTP_PASSWORD=real-mail-password-123\n"},
    )
    findings = scan_zip(path)
    assert any("疑似密钥" in item for item in findings)


def test_production_builder_writes_manifest_and_sha256sums(tmp_path):
    output = tmp_path / "production.zip"
    result = build(output)
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "RELEASE_MANIFEST.json" in names
        assert "SHA256SUMS.txt" in names
        assert "requirements.lock" in names
        assert "run_waitress.py" in names
        assert "scripts/windows/start_stock_server.cmd" in names
        assert not any(".venv" in name.split("/") for name in names)
        assert not any(name.endswith((".db", ".sqlite", ".sqlite3", ".key", ".pem", ".pfx", ".p12")) for name in names)
    assert scan_zip(output) == []
