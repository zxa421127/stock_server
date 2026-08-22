# -*- coding: utf-8 -*-
"""Safe plan-catalog delta and SQLite synchronization helpers.

This module has no command-line entry point.
Production deployment must invoke it only through a separately guarded
production migration workflow.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from services.plan_catalog import (
    DEFAULT_PLANS,
)

from tools.db.verify_plan_catalog import (
    collect_plan_catalog_drift_from_db,
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

MANAGED_FIELDS = frozenset(
    (
        *TEXT_FIELDS,
        *INTEGER_FIELDS,
        "scopes",
        "status",
    )
)

STRUCTURAL_DRIFT_FIELDS = frozenset(
    {
        "missing_plan",
        "legacy_plan_present",
    }
)


def catalog_by_code() -> dict[str, dict[str, Any]]:

    result = {
        str(plan["plan_code"]):
        dict(plan)

        for plan in DEFAULT_PLANS
    }

    if (
        len(result)
        != len(DEFAULT_PLANS)
    ):
        raise RuntimeError(
            "duplicate plan_code in catalog"
        )

    return result


def collect_delta(
    db_file: str | Path,
) -> list[dict[str, Any]]:

    path = Path(
        db_file
    ).resolve()

    return (
        collect_plan_catalog_drift_from_db(
            path
        )
    )


def assert_delta_is_field_only(
    delta: list[dict[str, Any]],
) -> None:

    for item in delta:

        field = str(
            item.get(
                "field",
                "",
            )
        )

        if field in STRUCTURAL_DRIFT_FIELDS:
            raise RuntimeError(
                "structural plan drift requires "
                "an explicit migration: "
                + field
            )

        if field not in MANAGED_FIELDS:
            raise RuntimeError(
                "unsupported plan drift field: "
                + field
            )


def _normalize_scopes(
    value: Any,
) -> tuple[str, ...]:

    if isinstance(
        value,
        str,
    ):

        value = json.loads(
            value
        )

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        raise RuntimeError(
            "invalid scopes value"
        )

    return tuple(
        sorted(
            str(item)
            for item in value
        )
    )


def _normalize(
    field: str,
    value: Any,
):

    if field in INTEGER_FIELDS:
        return int(value)

    if field in TEXT_FIELDS:
        return str(
            value
            if value is not None
            else ""
        )

    if field == "scopes":
        return _normalize_scopes(
            value
        )

    if field == "status":
        return str(
            value
            or ""
        ).strip().lower()

    return value


def _catalog_raw_value(
    plan: dict[str, Any],
    field: str,
):

    if field == "status":
        return "active"

    if field == "scopes":
        return json.dumps(
            plan["scopes"],
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

    return plan[field]


def quick_check(
    db_file: str | Path,
) -> None:

    path = Path(
        db_file
    ).resolve()

    uri = (
        "file:"
        + path.as_posix()
        + "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=30,
    )

    try:

        connection.execute(
            "PRAGMA query_only=ON"
        )

        rows = [
            str(row[0])
            for row in connection.execute(
                "PRAGMA quick_check"
            ).fetchall()
        ]

        if rows != ["ok"]:
            raise RuntimeError(
                "SQLite quick_check failed"
            )

    finally:

        connection.close()


def online_backup(
    source_db: str | Path,
    backup_db: str | Path,
) -> Path:

    source_path = Path(
        source_db
    ).resolve()

    backup_path = Path(
        backup_db
    ).resolve()

    if backup_path.exists():
        raise RuntimeError(
            "backup already exists: "
            + str(backup_path)
        )

    backup_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    source_uri = (
        "file:"
        + source_path.as_posix()
        + "?mode=ro"
    )

    source = sqlite3.connect(
        source_uri,
        uri=True,
        timeout=30,
    )

    destination = sqlite3.connect(
        str(backup_path),
        timeout=30,
    )

    try:

        source.execute(
            "PRAGMA query_only=ON"
        )

        source.backup(
            destination,
            pages=256,
            sleep=0.05,
        )

        destination.commit()

    finally:

        destination.close()
        source.close()


    quick_check(
        backup_path
    )

    return backup_path


def apply_field_delta(
    db_file: str | Path,
    *,
    backup_db: str | Path,
) -> dict[str, Any]:

    path = Path(
        db_file
    ).resolve()

    before_delta = collect_delta(
        path
    )

    assert_delta_is_field_only(
        before_delta
    )


    if not before_delta:

        return {
            "changed": False,
            "drift_before": 0,
            "drift_after": 0,
            "changed_plan_count": 0,
            "changed_field_count": 0,
            "backup_db": None,
        }


    quick_check(
        path
    )


    backup_path = online_backup(
        path,
        backup_db,
    )


    catalog = catalog_by_code()


    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}


    for item in before_delta:

        code = str(
            item["plan_code"]
        )

        if code not in catalog:
            raise RuntimeError(
                "drift refers to non-catalog plan: "
                + code
            )

        grouped.setdefault(
            code,
            [],
        ).append(
            dict(item)
        )


    rw_uri = (
        "file:"
        + path.as_posix()
        + "?mode=rw"
    )

    connection = sqlite3.connect(
        rw_uri,
        uri=True,
        timeout=30,
        isolation_level=None,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    committed = False

    try:

        connection.execute(
            "PRAGMA busy_timeout=30000"
        )

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        try:

            for code, items in grouped.items():

                row = connection.execute(
                    """
                    SELECT *
                    FROM plans
                    WHERE plan_code = ?
                    """,
                    (code,),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        "plan disappeared during sync: "
                        + code
                    )


                current = dict(
                    row
                )

                assignments = []

                parameters = []


                for item in items:

                    field = str(
                        item["field"]
                    )

                    expected_old = (
                        item.get(
                            "db"
                        )
                    )


                    actual_old = _normalize(
                        field,
                        current.get(
                            field
                        ),
                    )


                    if (
                        actual_old
                        != expected_old
                    ):
                        raise RuntimeError(
                            "plan changed concurrently: "
                            + code
                            + "."
                            + field
                        )


                    assignments.append(
                        field
                        + " = ?"
                    )

                    parameters.append(
                        _catalog_raw_value(
                            catalog[code],
                            field,
                        )
                    )


                parameters.append(
                    code
                )


                cursor = connection.execute(
                    (
                        "UPDATE plans SET "
                        + ", ".join(
                            assignments
                        )
                        + " WHERE plan_code = ?"
                    ),
                    parameters,
                )


                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "unexpected update rowcount "
                        + code
                        + "="
                        + str(
                            cursor.rowcount
                        )
                    )


            connection.commit()

            committed = True


        except Exception:

            if connection.in_transaction:
                connection.rollback()

            raise


    finally:

        connection.close()


    if not committed:
        raise RuntimeError(
            "plan sync transaction not committed"
        )


    quick_check(
        path
    )


    after_delta = collect_delta(
        path
    )


    if after_delta:
        raise RuntimeError(
            "plan catalog drift remains after sync"
        )


    backup_delta = collect_delta(
        backup_path
    )


    if len(
        backup_delta
    ) != len(
        before_delta
    ):
        raise RuntimeError(
            "backup does not preserve pre-sync drift"
        )


    return {
        "changed": True,
        "drift_before":
            len(
                before_delta
            ),
        "drift_after": 0,
        "changed_plan_count":
            len(grouped),
        "changed_field_count":
            len(
                before_delta
            ),
        "backup_db":
            str(
                backup_path
            ),
    }
