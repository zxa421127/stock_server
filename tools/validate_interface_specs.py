# -*- coding: utf-8 -*-
"""Validate active administrator interface specifications."""
from __future__ import annotations

import argparse
import json

from services.market_interface_spec_service import MarketInterfaceSpecService


def main() -> int:
    parser = argparse.ArgumentParser(description="校验管理员市场接口测试规格")
    parser.add_argument("--require-official-tushare", action="store_true", help="要求所有Tushare接口均已按官网确认发布")
    args = parser.parse_args()
    service = MarketInterfaceSpecService()
    service.ensure_seed_release()
    report = service.validate_all_specs(require_official_tushare=args.require_official_tushare)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["invalid_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
