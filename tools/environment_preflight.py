# -*- coding: utf-8 -*-
"""Non-destructive preflight shared by production and cloud-test slots."""
from __future__ import annotations

import json
import sqlite3

import config
from db_utils import assert_schema_ready, close_thread_connection
from services.environment_guard import collect_environment_errors, describe_environment
from services.redis_backend import get_redis


def run() -> dict[str, object]:
    checks: dict[str, object] = {}

    identity_errors = collect_environment_errors(config, require_enabled=True)
    checks["environment_identity"] = {
        "ok": not identity_errors,
        "errors": identity_errors,
        "actual": describe_environment(config),
    }

    try:
        assert_schema_ready()
        checks["database_schema"] = {"ok": True}
    except Exception as exc:
        checks["database_schema"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        close_thread_connection()

    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=3)
        try:
            integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        finally:
            conn.close()
        checks["database_integrity"] = {"ok": integrity == "ok", "result": integrity}
    except Exception as exc:
        checks["database_integrity"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        client = get_redis()
        redis_ok = bool(client is not None and client.ping())
        checks["redis"] = {"ok": redis_ok, "required": bool(config.REDIS_REQUIRED)}
    except Exception as exc:
        checks["redis"] = {
            "ok": False,
            "required": bool(config.REDIS_REQUIRED),
            "error": f"{type(exc).__name__}: {exc}",
        }

    overall = (
        bool(checks["environment_identity"]["ok"])
        and bool(checks["database_schema"]["ok"])
        and bool(checks["database_integrity"]["ok"])
        and (bool(checks["redis"]["ok"]) or not bool(config.REDIS_REQUIRED))
    )
    return {"ok": overall, "checks": checks}


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
