# -*- coding: utf-8 -*-
"""Fail a release when runtime artifacts, keys, certificates or plaintext secrets exist."""
from __future__ import annotations

import argparse
import re
from pathlib import Path, PurePosixPath
import zipfile

PROHIBITED_NAMES = {".env", "tokens.db", "audit_spool.db", "pyvenv.cfg"}
PROHIBITED_PARTS = {".git", ".idea", ".venv", "__pycache__", ".pytest_cache", "data", "logs"}
PROHIBITED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".key", ".pem", ".pfx", ".p12", ".jks", ".keystore", ".log",
}
SENSITIVE_ASSIGNMENTS = {
    "SECRET_KEY", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH", "ADMIN_TOTP_SECRET",
    "ADMIN_CLIENT_CERT_PROXY_SECRET", "ADMIN_CA_PASSWORD", "ADMIN_PFX_PASSWORD",
    "API_TOKEN_HASH_SECRET", "AUDIT_TOKEN_HMAC_SECRET", "CONTACT_VERIFICATION_HMAC_SECRET",
    "TUSHARE_TOKEN", "FEISHU_APP_SECRET", "KAIPANLA_TOKEN", "SMTP_PASSWORD",
    "SMS_VERIFY_WEBHOOK_SECRET",
}
ENV_ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)[ \t]*=[ \t]*(.*)$")
PYTHON_LITERAL_ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)[ \t]*=[ \t]*(['\"])(.*?)\2[ \t]*(?:#.*)?$")
TOKEN_PATTERNS = [
    re.compile(r"SK_STOCK_API_[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\b(?:sk|token)[-_][A-Za-z0-9_-]{24,}\b"),
]
PRIVATE_KEY_RE = re.compile(
    r"(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[ \t]*$"
)
SAFE_PREFIXES = ("请", "change", "change_me", "example", "please-", "your-", "replace-", "placeholder", "${", "<")


def _normalized_value(value: str) -> str:
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def _looks_like_plaintext_secret(value: str) -> bool:
    value = _normalized_value(value)
    if not value or len(value) < 8:
        return False
    lowered = value.lower()
    if lowered.startswith(SAFE_PREFIXES):
        return False
    if any(marker in lowered for marker in ("os.getenv(", "getenv(", "_get_str(", "_get_bool(")):
        return False
    return True


def _text_contains_secret(text: str, *, ignore_fixture_values: bool = False) -> bool:
    if PRIVATE_KEY_RE.search(text):
        return True
    if not ignore_fixture_values:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            env_match = ENV_ASSIGNMENT.match(stripped)
            if env_match and env_match.group(1) in SENSITIVE_ASSIGNMENTS:
                if _looks_like_plaintext_secret(env_match.group(2)):
                    return True
            python_match = PYTHON_LITERAL_ASSIGNMENT.match(stripped)
            if python_match and python_match.group(1) in SENSITIVE_ASSIGNMENTS:
                if _looks_like_plaintext_secret(python_match.group(3)):
                    return True
    if ignore_fixture_values:
        return False
    return any(pattern.search(text) for pattern in TOKEN_PATTERNS)


def _path_finding(filename: str) -> str | None:
    path = PurePosixPath(filename)
    parts = set(path.parts)
    name = path.name
    suffix = path.suffix.lower()
    if name == ".env.example":
        return None
    if name in PROHIBITED_NAMES:
        return f"禁止文件: {filename}"
    bad_parts = sorted(parts & PROHIBITED_PARTS)
    if bad_parts:
        return f"禁止目录({bad_parts[0]}): {filename}"
    if suffix in PROHIBITED_SUFFIXES:
        return f"禁止扩展名({suffix}): {filename}"
    return None


def scan_zip(path: Path, *, ignore_fixture_prefixes: tuple[str, ...] = ()) -> list[str]:
    findings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            path_issue = _path_finding(info.filename)
            if path_issue:
                findings.append(path_issue)
                continue
            if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                continue
            raw = archive.read(info)
            if raw.startswith(b"SQLite format 3\x00"):
                findings.append(f"禁止SQLite内容: {info.filename}")
                continue
            text = raw.decode("utf-8", errors="ignore")
            ignore_fixture_values = any(
                info.filename.startswith(prefix) for prefix in ignore_fixture_prefixes
            )
            if _text_contains_secret(text, ignore_fixture_values=ignore_fixture_values):
                marker = "PRIVATE KEY" if PRIVATE_KEY_RE.search(text) else "疑似密钥"
                findings.append(f"{marker}: {info.filename}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    parser.add_argument(
        "--ignore-fixture-prefix",
        action="append",
        default=[],
        help="仅对已知测试夹具目录忽略伪Token/伪密钥值；私钥块仍会被拒绝",
    )
    args = parser.parse_args()
    findings = scan_zip(
        Path(args.zip_path),
        ignore_fixture_prefixes=tuple(args.ignore_fixture_prefix),
    )
    if findings:
        print("\n".join(findings))
        return 1
    print("敏感信息扫描通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
