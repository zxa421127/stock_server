from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from services.plan_catalog import (
    DEFAULT_PLANS,
)

from tools.db.plan_catalog_sync import (
    apply_field_delta,
    assert_delta_is_field_only,
    collect_delta,
)


def _create_db(
    db_file: Path,
):

    connection = sqlite3.connect(
        db_file
    )

    try:

        connection.execute(
            """
            CREATE TABLE plans (
                plan_code TEXT PRIMARY KEY,
                plan_name TEXT,
                plan_type TEXT,
                duration_type TEXT,
                duration_days INTEGER,
                original_price_cent INTEGER,
                sale_price_cent INTEGER,
                quota_daily INTEGER,
                quota_per_minute INTEGER,
                max_symbols_per_request INTEGER,
                min_refresh_interval_sec INTEGER,
                scopes TEXT,
                status TEXT
            )
            """
        )


        for plan in DEFAULT_PLANS:

            connection.execute(
                """
                INSERT INTO plans (
                    plan_code,
                    plan_name,
                    plan_type,
                    duration_type,
                    duration_days,
                    original_price_cent,
                    sale_price_cent,
                    quota_daily,
                    quota_per_minute,
                    max_symbols_per_request,
                    min_refresh_interval_sec,
                    scopes,
                    status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    plan["plan_code"],
                    plan["plan_name"],
                    plan["plan_type"],
                    plan["duration_type"],
                    plan["duration_days"],
                    plan["original_price_cent"],
                    plan["sale_price_cent"],
                    plan["quota_daily"],
                    plan["quota_per_minute"],
                    plan["max_symbols_per_request"],
                    plan["min_refresh_interval_sec"],
                    json.dumps(
                        plan["scopes"],
                        ensure_ascii=False,
                    ),
                    "active",
                ),
            )


        connection.execute(
            """
            INSERT INTO plans (
                plan_code,
                plan_name,
                plan_type,
                duration_type,
                duration_days,
                original_price_cent,
                sale_price_cent,
                quota_daily,
                quota_per_minute,
                max_symbols_per_request,
                min_refresh_interval_sec,
                scopes,
                status
            )
            VALUES (
                'custom_plan',
                'Custom',
                'custom',
                'internal',
                1,
                0,
                0,
                1,
                1,
                1,
                1,
                '[]',
                'active'
            )
            """
        )


        connection.commit()

    finally:

        connection.close()


def test_collect_delta_detects_only_changed_fields(
    tmp_path,
):

    db_file = (
        tmp_path
        / "plans.db"
    )

    _create_db(
        db_file
    )


    connection = sqlite3.connect(
        db_file
    )

    try:

        connection.execute(
            """
            UPDATE plans
            SET quota_per_minute = ?
            WHERE plan_code = ?
            """,
            (
                999,
                "general_month",
            ),
        )

        connection.execute(
            """
            UPDATE plans
            SET quota_daily = ?
            WHERE plan_code = ?
            """,
            (
                999,
                "special_year",
            ),
        )

        connection.commit()

    finally:

        connection.close()


    delta = collect_delta(
        db_file
    )


    keys = {
        (
            item["plan_code"],
            item["field"],
        )
        for item in delta
    }


    assert keys == {
        (
            "general_month",
            "quota_per_minute",
        ),
        (
            "special_year",
            "quota_daily",
        ),
    }


def test_apply_field_delta_backs_up_and_restores_catalog(
    tmp_path,
):

    db_file = (
        tmp_path
        / "plans.db"
    )

    backup_db = (
        tmp_path
        / "backup"
        / "before.db"
    )


    _create_db(
        db_file
    )


    connection = sqlite3.connect(
        db_file
    )

    try:

        connection.execute(
            """
            UPDATE plans
            SET
                quota_per_minute = ?,
                quota_daily = ?
            WHERE plan_code = ?
            """,
            (
                999,
                999,
                "general_month",
            ),
        )

        custom_before = (
            connection.execute(
                """
                SELECT *
                FROM plans
                WHERE plan_code =
                    'custom_plan'
                """
            ).fetchone()
        )

        connection.commit()

    finally:

        connection.close()


    result = apply_field_delta(
        db_file,
        backup_db=backup_db,
    )


    assert result["changed"] is True

    assert (
        result["changed_plan_count"]
        == 1
    )

    assert (
        result["changed_field_count"]
        == 2
    )

    assert (
        collect_delta(
            db_file
        )
        == []
    )

    assert (
        len(
            collect_delta(
                backup_db
            )
        )
        == 2
    )


    connection = sqlite3.connect(
        db_file
    )

    try:

        custom_after = (
            connection.execute(
                """
                SELECT *
                FROM plans
                WHERE plan_code =
                    'custom_plan'
                """
            ).fetchone()
        )

    finally:

        connection.close()


    assert (
        custom_after
        == custom_before
    )


def test_missing_builtin_plan_requires_explicit_migration(
    tmp_path,
):

    db_file = (
        tmp_path
        / "plans.db"
    )

    backup_db = (
        tmp_path
        / "backup.db"
    )


    _create_db(
        db_file
    )


    connection = sqlite3.connect(
        db_file
    )

    try:

        connection.execute(
            """
            DELETE FROM plans
            WHERE plan_code =
                'general_month'
            """
        )

        connection.commit()

    finally:

        connection.close()


    delta = collect_delta(
        db_file
    )


    with pytest.raises(
        RuntimeError,
        match="structural plan drift",
    ):

        assert_delta_is_field_only(
            delta
        )


    with pytest.raises(
        RuntimeError,
        match="structural plan drift",
    ):

        apply_field_delta(
            db_file,
            backup_db=backup_db,
        )


    assert not backup_db.exists()


def test_no_drift_is_noop_without_backup(
    tmp_path,
):

    db_file = (
        tmp_path
        / "plans.db"
    )

    backup_db = (
        tmp_path
        / "backup.db"
    )


    _create_db(
        db_file
    )


    result = apply_field_delta(
        db_file,
        backup_db=backup_db,
    )


    assert result == {
        "changed": False,
        "drift_before": 0,
        "drift_after": 0,
        "changed_plan_count": 0,
        "changed_field_count": 0,
        "backup_db": None,
    }


    assert not backup_db.exists()
