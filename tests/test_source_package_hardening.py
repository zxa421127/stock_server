from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from tools.release.build_source_package import build
from tools.security.scan_release_secrets import scan_zip


def test_source_builder_creates_shareable_development_package(tmp_path):
    output = tmp_path / "source.zip"
    result = build(output)
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert ".env.example" in names
        assert "requirements.txt" in names
        assert "requirements-dev.txt" in names
        assert "tests/test_windows_script_portability.py" in names
        assert "e2e_tests/01_deployment/run.bat" in names
        assert "SOURCE_MANIFEST.json" in names
        assert "SHA256SUMS.txt" in names
        assert not any(part in {".venv", ".idea", "data", "logs", "dist"} for name in names for part in Path(name).parts)
        assert ".env" not in names
        assert not any(name.endswith((".db", ".sqlite", ".sqlite3", ".key", ".pem", ".pfx", ".p12", ".log")) for name in names)

    assert scan_zip(output, ignore_fixture_prefixes=("tests/",)) == []

def test_source_scan_still_rejects_private_keys_inside_tests(tmp_path):
    path = tmp_path / "bad-source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("tests/leaked_key.py", "-----BEGIN PRIVATE KEY-----\nabc\n")
    findings = scan_zip(path, ignore_fixture_prefixes=("tests/",))
    assert any("PRIVATE KEY" in item for item in findings)



def test_secret_scanner_cli_can_explicitly_ignore_known_test_fixtures(tmp_path, monkeypatch, capsys):
    from tools.security import scan_release_secrets

    output = tmp_path / "source.zip"
    build(output)
    monkeypatch.setattr(
        "sys.argv",
        [
            "scan_release_secrets",
            str(output),
            "--ignore-fixture-prefix",
            "tests/",
        ],
    )
    assert scan_release_secrets.main() == 0
    assert "敏感信息扫描通过" in capsys.readouterr().out
