# -*- coding: utf-8 -*-
from pathlib import Path
import zipfile

from tools.security.scan_release_secrets import scan_zip


def _zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_release_scanner_ignores_empty_examples_and_getenv_code(tmp_path):
    path = _zip(
        tmp_path / "safe.zip",
        {
            ".env.example": "FEISHU_APP_SECRET=\nKAIPANLA_TOKEN=\nSECRET_KEY=请改成随机长字符串\n",
            "config.py": 'SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-secret")\n',
        },
    )
    assert scan_zip(path) == []


def test_release_scanner_detects_plaintext_secret_assignment(tmp_path):
    path = _zip(tmp_path / "bad.zip", {"settings.env": "TUSHARE_TOKEN=real-secret-token-123456789\n"})
    assert any("疑似密钥" in item for item in scan_zip(path))
