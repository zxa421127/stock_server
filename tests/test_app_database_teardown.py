# -*- coding: utf-8 -*-
from pathlib import Path


def test_app_context_teardown_closes_thread_database_connection():
    source = Path("app.py").read_text(encoding="utf-8")

    assert "from db_utils import assert_schema_ready, close_thread_connection, get_conn, init_db" in source
    assert "@app.teardown_appcontext" in source
    assert "close_thread_connection()" in source
