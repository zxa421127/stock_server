# -*- coding: utf-8 -*-
"""Audit Windows scripts for encoding, line-ending and stale-command problems."""
from __future__ import annotations

import argparse
from pathlib import Path

SCRIPT_SUFFIXES = {".bat", ".cmd", ".ps1"}
IGNORED_PARTS = {".git", ".venv", ".idea", "__pycache__", "docs"}


def audit(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCRIPT_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in rel.parts):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            findings.append(f"不是有效UTF-8: {rel}: {exc}")
            continue
        if b"\n" in raw and raw.count(b"\n") != raw.count(b"\r\n"):
            findings.append(f"不是Windows CRLF换行: {rel}")
        if path.suffix.lower() == ".ps1" and any(ord(char) > 127 for char in text):
            if not raw.startswith(b"\xef\xbb\xbf"):
                findings.append(f"含中文的PowerShell缺少UTF-8 BOM: {rel}")
        lowered = text.lower()
        if "python app.py" in lowered:
            findings.append(f"仍提示旧启动入口python app.py: {rel}")
        if "tests.test_e2e_tests_two_tier_tokens" in text:
            findings.append(f"引用不存在的测试模块: {rel}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = audit(root)
    if findings:
        print("\n".join(findings))
        return 1
    print("Windows脚本编码、换行和入口检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
