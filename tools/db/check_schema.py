# -*- coding: utf-8 -*-
from db_utils import assert_schema_ready, close_thread_connection


def main() -> int:
    assert_schema_ready()
    close_thread_connection()
    print("数据库结构检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
