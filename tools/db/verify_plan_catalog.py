# -*- coding: utf-8 -*-
"""Read-only deployment gate for built-in plan catalog/database consistency."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values

import config

from db_utils import get_plan_by_code
from services.plan_catalog import (
    DEFAULT_PLANS,
    LEGACY_PUBLIC_PLAN_MIGRATION,
)


TEXT_FIELDS = (
    "plan_name",
    "plan_type",
    "duration_type",
)

INTEGER_FIELDS = (
    "duration_days",
    "original_price_cent",
    "sale_price_cent",
    "quota_daily",
    "quota_per_minute",
    "max_symbols_per_request",
    "min_refresh_interval_sec",
)


def _normalize_scopes(value: Any):

    if isinstance(value, str):

        try:
            value = json.loads(value)
        except Exception:
            return (
                "<invalid-scopes-json>",
                value,
            )

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        return (
            "<invalid-scopes>",
            repr(value),
        )

    return tuple(
        sorted(
            str(item)
            for item in value
        )
    )


def _normalize_value(
    field: str,
    value: Any,
):

    if field in INTEGER_FIELDS:

        try:
            return int(value)
        except (TypeError, ValueError):
            return (
                "<invalid-int>",
                repr(value),
            )

    if field in TEXT_FIELDS:
        return str(
            value
            if value is not None
            else ""
        )

    return value


def collect_plan_catalog_drift(
    getter: Callable[[str], dict | None] | None = None,
) -> list[dict[str, Any]]:
    """Return differences without mutating database state."""

    if getter is None:
        getter = get_plan_by_code

    drift: list[dict[str, Any]] = []

    for catalog_plan in DEFAULT_PLANS:

        code = str(
            catalog_plan["plan_code"]
        )

        db_plan = getter(
            code
        )

        if db_plan is None:

            drift.append(
                {
                    "plan_code": code,
                    "field": "missing_plan",
                    "db": None,
                    "catalog": "present",
                }
            )

            continue

        for field in (
            *TEXT_FIELDS,
            *INTEGER_FIELDS,
        ):

            db_value = _normalize_value(
                field,
                db_plan.get(field),
            )

            catalog_value = _normalize_value(
                field,
                catalog_plan.get(field),
            )

            if db_value != catalog_value:

                drift.append(
                    {
                        "plan_code": code,
                        "field": field,
                        "db": db_value,
                        "catalog": catalog_value,
                    }
                )

        db_scopes = _normalize_scopes(
            db_plan.get(
                "scopes"
            )
        )

        catalog_scopes = _normalize_scopes(
            catalog_plan.get(
                "scopes"
            )
        )

        if db_scopes != catalog_scopes:

            drift.append(
                {
                    "plan_code": code,
                    "field": "scopes",
                    "db": db_scopes,
                    "catalog": catalog_scopes,
                }
            )

        db_status = str(
            db_plan.get(
                "status"
            )
            or ""
        ).strip().lower()

        if db_status != "active":

            drift.append(
                {
                    "plan_code": code,
                    "field": "status",
                    "db": db_status,
                    "catalog": "active",
                }
            )


    # ?????????????
    # ???????????????????
    for legacy_code in sorted(
        LEGACY_PUBLIC_PLAN_MIGRATION
    ):

        if getter(
            legacy_code
        ) is not None:

            drift.append(
                {
                    "plan_code": legacy_code,
                    "field": "legacy_plan_present",
                    "db": "present",
                    "catalog": "removed",
                }
            )

    return drift


def _read_only_sqlite_uri(
    db_file: Path,
) -> str:

    path = db_file.resolve()

    return (
        "file:"
        + path.as_posix()
        + "?mode=ro"
    )


def collect_plan_catalog_drift_from_db(
    db_file: str | Path,
) -> list[dict[str, Any]]:

    path = Path(
        db_file
    ).resolve()

    if not path.is_file():

        raise FileNotFoundError(
            f"database file does not exist: {path}"
        )

    connection = sqlite3.connect(
        _read_only_sqlite_uri(path),
        uri=True,
        timeout=3,
    )

    connection.row_factory = sqlite3.Row

    try:

        connection.execute(
            "PRAGMA query_only = ON"
        )

        def getter(
            plan_code: str,
        ) -> dict | None:

            row = connection.execute(
                """
                SELECT *
                FROM plans
                WHERE plan_code = ?
                LIMIT 1
                """,
                (plan_code,),
            ).fetchone()

            if row is None:
                return None

            return dict(row)

        return collect_plan_catalog_drift(
            getter
        )

    finally:

        connection.close()


def resolve_project_db_file(
    project_root: str | Path,
) -> Path:

    root = Path(
        project_root
    ).resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            f"project root does not exist: {root}"
        )

    env_file = root / ".env"

    if not env_file.is_file():
        raise FileNotFoundError(
            f"project env file does not exist: {env_file}"
        )

    values = dotenv_values(
        env_file
    )

    data_raw = values.get(
        "DATA_DIR"
    )

    if data_raw is None:
        data_raw = str(
            root / "data"
        )

    data_dir = Path(
        str(data_raw)
    )

    if not data_dir.is_absolute():
        data_dir = root / data_dir


    db_raw = values.get(
        "DB_FILE"
    )

    if db_raw is None:
        db_raw = str(
            data_dir / "tokens.db"
        )

    db_file = Path(
        str(db_raw)
    )

    if not db_file.is_absolute():
        db_file = root / db_file

    return db_file.resolve()


def _parse_args(
    argv: list[str] | None = None,
):

    parser = argparse.ArgumentParser(
        description="Read-only plan catalog database gate"
    )

    targets = parser.add_mutually_exclusive_group()

    targets.add_argument(
        "--db-file",
        default="",
    )

    targets.add_argument(
        "--project-root",
        default="",
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[str] | None = None,
) -> int:

    args = _parse_args(
        argv
    )

    print(
        "DEPLOYMENT_SLOT="
        + str(
            getattr(
                config,
                "DEPLOYMENT_SLOT",
                "",
            )
        )
    )

    print(
        "EXPECTED_BUILTIN_PLAN_COUNT="
        + str(len(DEFAULT_PLANS))
    )

    try:

        if args.project_root:

            db_file = resolve_project_db_file(
                args.project_root
            )

            source_name = "project-root"

        elif args.db_file:

            db_file = Path(
                args.db_file
            ).resolve()

            source_name = "explicit-db-file"

        else:

            db_file = Path(
                config.DB_FILE
            ).resolve()

            source_name = "current-config"


        print(
            "TARGET_DB_SOURCE="
            + source_name
        )

        print(
            "TARGET_DB_MODE=READ_ONLY"
        )

        print(
            "TARGET_DB_FILE="
            + str(db_file)
        )


        drift = collect_plan_catalog_drift_from_db(
            db_file
        )


    except Exception as exc:

        print(
            "PLAN_CATALOG_DB_SYNC=ERROR"
        )

        print(
            "ERROR_TYPE="
            + type(exc).__name__
        )

        print(
            "ERROR_MESSAGE="
            + str(exc)
        )

        return 2


    if drift:

        for item in drift:

            print(
                "PLAN_DRIFT="
                + json.dumps(
                    item,
                    ensure_ascii=False,
                    default=str,
                    separators=(",", ":"),
                )
            )

        print(
            f"PLAN_DRIFT_COUNT={len(drift)}"
        )

        print(
            "PLAN_CATALOG_DB_SYNC=FAIL"
        )

        return 1


    print(
        "PLAN_DRIFT_COUNT=0"
    )

    print(
        "PLAN_CATALOG_DB_SYNC=PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )