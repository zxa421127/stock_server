# -*- coding: utf-8 -*-
"""Inspect or compatibly extend the Feishu Kaipanla bidding table schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.feishu.bitable import get_bitable_manager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查飞书竞价表字段；默认只读，--apply 仅新增缺失字段，不修改或删除现有字段。"
    )
    parser.add_argument("--apply", action="store_true", help="创建缺失字段")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = get_bitable_manager().check_bidding_schema(create_missing=args.apply)
    except Exception as exc:
        report = {"ok": False, "mode": "apply" if args.apply else "dry-run", "error": str(exc)}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    report["mode"] = "apply" if args.apply else "dry-run"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
