# -*- coding: utf-8 -*-
"""Run non-destructive production checks before starting the web service."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import config
from db_utils import assert_schema_ready, close_thread_connection
from services.environment_guard import collect_environment_errors, describe_environment
from services.production_readiness import collect_configuration_errors
from services.redis_backend import get_redis
from tools.db.verify_plan_catalog import collect_plan_catalog_drift_from_db


def _directory_check(path: Path) -> dict:
    result = {"path": str(path), "exists": path.exists(), "writable": False, "free_bytes": 0}
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".preflight-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        result["writable"] = True
        result["free_bytes"] = int(shutil.disk_usage(path).free)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run() -> dict:
    checks: dict[str, object] = {}
    identity_errors = collect_environment_errors(config, require_enabled=True)
    checks["environment_identity"] = {
        "ok": not identity_errors,
        "errors": identity_errors,
        "actual": describe_environment(config),
    }
    config_errors = collect_configuration_errors(config, redis_getter=get_redis)
    checks["configuration"] = {"ok": not config_errors, "errors": config_errors}

    try:
        assert_schema_ready()
        checks["database_schema"] = {"ok": True}
        from services.admin_client_certificate import count_active_certificates
        active_certificates = count_active_certificates(admin_username=config.ADMIN_USERNAME)
        checks["admin_client_certificates"] = {
            "ok": active_certificates > 0,
            "active_count": active_certificates,
        }
    except Exception as exc:
        checks["database_schema"] = {"ok": False, "error": str(exc)}
        checks["admin_client_certificates"] = {"ok": False, "error": str(exc)}
    finally:
        close_thread_connection()

    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=3)
        integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        conn.close()
        checks["database_integrity"] = {"ok": integrity == "ok", "result": integrity}
    except Exception as exc:
        checks["database_integrity"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        # FIX3C_PLAN_CATALOG_GATE_V1
        plan_drift = collect_plan_catalog_drift_from_db(
            Path(config.DB_FILE)
        )
        checks["plan_catalog"] = {
            "ok": not plan_drift,
            "drift_count": len(plan_drift),
            "drift": plan_drift,
            "read_only": True,
        }
    except Exception as exc:
        checks["plan_catalog"] = {
            "ok": False,
            "drift_count": -1,
            "read_only": True,
            "error": f"{type(exc).__name__}: {exc}",
        }

    try:
        client = get_redis()
        redis_ok = bool(client is not None and client.ping())
        checks["redis"] = {"ok": redis_ok, "required": bool(config.REDIS_REQUIRED)}
    except Exception as exc:
        checks["redis"] = {"ok": False, "required": bool(config.REDIS_REQUIRED), "error": str(exc)}

    checks["directories"] = {
        "data": _directory_check(Path(config.DATA_DIR)),
        "logs": _directory_check(Path(config.LOG_DIR)),
        "interface_specs": _directory_check(Path(config.BASE_DIR) / "interface_specs"),
    }
    dir_ok = all(bool(value.get("writable")) for value in checks["directories"].values())
    overall = (
        bool(checks["environment_identity"]["ok"])
        and bool(checks["configuration"]["ok"])
        and bool(checks["database_schema"]["ok"])
        and bool(checks["database_integrity"]["ok"])
        and bool(checks["plan_catalog"]["ok"])
        and bool(checks["admin_client_certificates"]["ok"])
        and (bool(checks["redis"]["ok"]) or not bool(config.REDIS_REQUIRED))
        and dir_ok
    )
    return {"ok": overall, "checks": checks}


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
