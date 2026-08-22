# -*- coding: utf-8 -*-
"""Install or rebuild the complete generated public API documentation."""
from __future__ import annotations

import argparse
import json

import db_utils
from services.api_doc_service import full_api_docs_status, sync_full_api_docs


def main() -> int:
    parser = argparse.ArgumentParser(description="同步完整自动生成API文档")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查当前安装状态，不重建文档",
    )
    args = parser.parse_args()

    db_utils.init_db()
    if args.check:
        result = full_api_docs_status()
    else:
        result = sync_full_api_docs(force=True)
        result["status"] = full_api_docs_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    status = full_api_docs_status()
    ok = (
        status["installed_version"] == status["expected_version"]
        and status["installed_count"] == status["expected_count"]
        and status.get("installed_fingerprint")
        == status.get("expected_fingerprint")
    )
    print()
    if ok:
        print(f"PASS: 完整{status['expected_count']}接口API文档已安装。")
        return 0
    print("FAIL: API文档数量、版本或目录指纹不匹配。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
