# -*- coding: utf-8 -*-
"""Build a deterministic production ZIP from a strict allow-list."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_FILES = {
    "app.py", "wsgi.py", "run_waitress.py", "config.py", "db_utils.py", "gunicorn.conf.py",
    "requirements.txt", "requirements.lock", ".env.example", "README.md",
    "SECURITY_FIX_CHANGELOG.md", "TEST_REPORT.txt", "docs/README.md", "docs/CHANGELOG.md",
    "docs/SECURITY_REMEDIATION.md", "scripts/windows/start_stock_server.cmd",
    "tools/__init__.py", "tools/admin_api_test_worker.py", "tools/api_doc_status_worker.py",
    "tools/audit_cleanup_worker.py", "tools/feishu_worker.py", "tools/kaipanla_snapshot_worker.py",
    "tools/production_preflight.py", "tools/environment_preflight.py",
    "tools/tushare_spec_monitor_worker.py",
    "tools/sync_tushare_interface_specs.py", "tools/audit_interface_specs.py",
    "tools/validate_interface_specs.py", "tools/sync_full_api_docs.py",
}
ALLOWED_DIRS = {
    "routes", "services", "integrations", "middleware", "utils", "templates", "static",
    "interface_specs", "deploy", "tools/db", "tools/security", "tools/release",
    "docs/operations", "docs/security", "docs/architecture", "docs/features",
}
DENIED_PARTS = {
    ".git", ".idea", ".venv", "__pycache__", ".pytest_cache", "data", "logs",
    "tests", "e2e_tests", "archive", "debug", "manual_tests", "market_data_optimization",
}
DENIED_NAMES = {".env", "tokens.db", "audit_spool.db", "pyvenv.cfg"}
DENIED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".pfx", ".p12", ".jks", ".log"}
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _allowed(path: Path) -> bool:
    if path.is_symlink():
        return False
    rel = path.relative_to(ROOT)
    if path.name in DENIED_NAMES or path.suffix.lower() in DENIED_SUFFIXES or any(part in DENIED_PARTS for part in rel.parts):
        return False
    posix = rel.as_posix()
    if posix in ALLOWED_FILES:
        return True
    return any(posix == directory or posix.startswith(directory + "/") for directory in ALLOWED_DIRS)


def _write_file(archive: zipfile.ZipFile, rel: str, data: bytes) -> None:
    info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o644 & 0xFFFF) << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(output: Path) -> dict:
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and _allowed(path))
    manifest = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            _write_file(archive, rel, data)
            manifest.append({"path": rel, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        manifest_data = json.dumps({"files": manifest}, ensure_ascii=False, indent=2).encode("utf-8")
        _write_file(archive, "RELEASE_MANIFEST.json", manifest_data)
        sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest).encode("utf-8")
        _write_file(archive, "SHA256SUMS.txt", sums)
    from tools.security.scan_release_secrets import scan_zip
    findings = scan_zip(output)
    if findings:
        output.unlink(missing_ok=True)
        raise RuntimeError("生产包敏感信息扫描失败: " + "; ".join(findings))
    return {
        "output": str(output),
        "file_count": len(files),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "dist" / "stock-server-production.zip"))
    args = parser.parse_args()
    result = build(Path(args.output).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
