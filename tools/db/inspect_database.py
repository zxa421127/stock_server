# -*- coding: utf-8 -*-
"""Print table names and row counts without exposing token values."""
from db_utils import get_conn, init_db


def main() -> None:
    init_db()
    conn = get_conn()
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
