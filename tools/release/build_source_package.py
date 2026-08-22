# -*- coding: utf-8 -*-
"""Build a shareable development-source ZIP without runtime data or credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from tools.security.scan_release_secrets import scan_zip

ROOT = Path(__file__).resolve().parents[2]
DENIED_PARTS = {
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "data-dev",
    "data-test",
    "logs",
    "logs-dev",
    "dist",
    "build",
    "patch_backups",
    "node_modules",
}
DENIED_NAMES = {
    ".env",
    "pyvenv.cfg",
    "membership_test_tokens.json",
    "interface_test_token.txt",
    "RELEASE_MANIFEST.json",
    "SOURCE_MANIFEST.json",
    "DEV_SOURCE_MANIFEST.json",
    "TEST_REPORT.txt",
    "SHA256SUMS.txt",
}
DENIED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".key",
    ".pem",
    ".pfx",
    ".p12",
    ".jks",
    ".keystore",
    ".log",
    ".zip",
    ".7z",
    ".rar",
    ".pyc",
}
EXCLUDED_PREFIXES = {
    "docs/archive",
    "security/admin-client-ca",
}
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _allowed(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    rel = path.relative_to(ROOT)
    posix = rel.as_posix()
    if path.name in DENIED_NAMES or path.suffix.lower() in DENIED_SUFFIXES:
        return False
    if any(part in DENIED_PARTS for part in rel.parts):
        return False
    if any(posix == prefix or posix.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES):
        return False
    return True


def _write_file(archive: zipfile.ZipFile, rel: str, data: bytes) -> None:
    info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o644 & 0xFFFF) << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(output: Path) -> dict[str, object]:
    output = output.resolve()
    files = sorted(path for path in ROOT.rglob("*") if _allowed(path) and path.resolve() != output)
    manifest: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w") as archive:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            _write_file(archive, rel, data)
            manifest.append(
                {
                    "path": rel,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

        manifest_data = json.dumps(
            {"package_type": "development-source", "files": manifest},
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        _write_file(archive, "SOURCE_MANIFEST.json", manifest_data)
        sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest).encode("utf-8")
        _write_file(archive, "SHA256SUMS.txt", sums)

    findings = scan_zip(output, ignore_fixture_prefixes=("tests/",))
    if findings:
        output.unlink(missing_ok=True)
        raise RuntimeError("源码包敏感信息扫描失败: " + "; ".join(findings))

    return {
        "output": str(output),
        "file_count": len(files),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="构建可安全分享的完整开发源码包")
    parser.add_argument("--output", default=str(ROOT / "dist" / "stock-server-source.zip"))
    args = parser.parse_args()
    result = build(Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
