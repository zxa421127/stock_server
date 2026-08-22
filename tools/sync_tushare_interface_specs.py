# -*- coding: utf-8 -*-
"""Legacy CLI: detect Tushare official changes and create admin alerts only."""
from __future__ import annotations

import argparse
import json

from db_utils import init_db
from services.tushare_spec_monitor_service import get_tushare_spec_monitor_service


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查Tushare官网接口定义并生成变化提醒；不生成候选、不自动发布",
    )
    parser.add_argument(
        "--api", action="append", default=[],
        help="仅检查指定接口，可重复；省略则检查全部Tushare接口",
    )
    args = parser.parse_args()
    init_db()
    result = get_tushare_spec_monitor_service().scan(args.api or None, trigger="legacy_cli")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("complete_scan") else 2


if __name__ == "__main__":
    raise SystemExit(main())
