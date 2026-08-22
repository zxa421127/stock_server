# -*- coding: utf-8 -*-
"""Administrator CLI for Tushare spec scan and alert-driven candidate creation."""
from __future__ import annotations

import argparse
import json

from db_utils import init_db
from services.tushare_spec_monitor_service import get_tushare_spec_monitor_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Tushare官网规格监控")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="检查官网变化，不修改正式规格")
    scan.add_argument("--api", action="append", default=[])
    status = sub.add_parser("status", help="查看扫描状态和待处理提醒")
    status.add_argument("--limit", type=int, default=100)
    sync = sub.add_parser("sync-alerts", help="重新抓取所选提醒并生成候选")
    sync.add_argument("--alert-id", action="append", type=int, required=True)
    args = parser.parse_args()
    init_db()
    service = get_tushare_spec_monitor_service()
    if args.command == "scan":
        result = service.scan(args.api or None, trigger="manual_cli")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("complete_scan") else 2
    if args.command == "status":
        result = service.dashboard()
        result["alerts"] = result.get("alerts", [])[: max(1, args.limit)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = service.create_candidate_for_alerts(args.alert_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("complete_sync") else 2


if __name__ == "__main__":
    raise SystemExit(main())
