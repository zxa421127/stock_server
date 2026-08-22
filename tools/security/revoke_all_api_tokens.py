# -*- coding: utf-8 -*-
"""Emergency revocation for all user API tokens."""
from __future__ import annotations

import argparse
from datetime import datetime

from db_utils import get_conn
from services.auth_context_cache import clear_auth_context_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="紧急吊销所有用户API Token")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != "REVOKE-ALL":
        parser.error("必须显式传入 --confirm REVOKE-ALL")
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "UPDATE api_keys SET status='revoked', rotated_at=? WHERE status='active'",
        (now,),
    )
    conn.commit()
    clear_auth_context_cache()
    print(f"已吊销 {int(cursor.rowcount or 0)} 个API Token。用户必须重新生成Token。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
