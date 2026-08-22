# -*- coding: utf-8 -*-
"""Manual Feishu integration test. Requires complete Feishu configuration."""
from db_utils import init_db
from services.feishu_sync_service import run_full_sync


if __name__ == "__main__":
    init_db()
    run_full_sync()
    print("飞书同步测试完成，请检查日志。")
