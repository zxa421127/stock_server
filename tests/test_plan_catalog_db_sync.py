# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from copy import deepcopy
from pathlib import Path

import tools.db.verify_plan_catalog as verifier

from services.plan_catalog import (
    DEFAULT_PLANS,
    LEGACY_PUBLIC_PLAN_MIGRATION,
)


def _catalog_rows():

    rows = {}

    for plan in DEFAULT_PLANS:

        row = deepcopy(
            plan
        )

        row["scopes"] = json.dumps(
            plan["scopes"],
            ensure_ascii=False,
        )

        row["status"] = "active"

        rows[
            plan["plan_code"]
        ] = row

    return rows


def _getter(rows):

    return lambda code: rows.get(
        code
    )


def _catalog_policy_value(
    plan_code,
    field,
):

    matches = [
        plan
        for plan in DEFAULT_PLANS
        if (
            plan["plan_code"]
            == plan_code
        )
    ]

    assert len(matches) == 1

    return matches[0][field]


def test_exact_catalog_has_no_drift():

    rows = _catalog_rows()

    assert verifier.collect_plan_catalog_drift(
        _getter(rows)
    ) == []


def test_quota_per_minute_drift_is_detected():

    rows = _catalog_rows()

    rows[
        "general_month"
    ][
        "quota_per_minute"
    ] = 1000

    drift = verifier.collect_plan_catalog_drift(
        _getter(rows)
    )

    assert any(
        item["plan_code"] == "general_month"
        and item["field"] == "quota_per_minute"
        and item["catalog"] == _catalog_policy_value("general_month", "quota_per_minute")
        for item in drift
    )


def test_scope_order_is_semantically_equal():

    rows = _catalog_rows()

    original = json.loads(
        rows[
            "special_month"
        ][
            "scopes"
        ]
    )

    rows[
        "special_month"
    ][
        "scopes"
    ] = json.dumps(
        list(
            reversed(
                original
            )
        ),
        ensure_ascii=False,
    )

    assert verifier.collect_plan_catalog_drift(
        _getter(rows)
    ) == []


def test_missing_and_legacy_plans_are_detected():

    rows = _catalog_rows()

    rows.pop(
        "special_year"
    )

    legacy_code = next(
        iter(
            LEGACY_PUBLIC_PLAN_MIGRATION
        )
    )

    rows[
        legacy_code
    ] = {
        "plan_code": legacy_code,
        "status": "active",
    }

    drift = verifier.collect_plan_catalog_drift(
        _getter(rows)
    )

    assert any(
        item["plan_code"] == "special_year"
        and item["field"] == "missing_plan"
        for item in drift
    )

    assert any(
        item["plan_code"] == legacy_code
        and item["field"] == "legacy_plan_present"
        for item in drift
    )


def test_init_plans_runs_post_migration_verifier():

    root = Path(
        __file__
    ).resolve().parents[1]

    text = (
        root
        / "tools"
        / "db"
        / "init_plans.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "tools.db.apply_two_tier_plans "
        "import main as apply_main"
    ) in text

    assert (
        "tools.db.verify_plan_catalog "
        "import main as verify_main"
    ) in text

    assert text.index(
        "apply_main()"
    ) < text.index(
        "verify_main()"
    )



def _write_catalog_sqlite(db_file):

    import sqlite3

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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        connection.commit()

    finally:

        connection.close()


def test_external_sqlite_reader_is_read_only(
    tmp_path,
):

    db_file = tmp_path / "plans.db"

    _write_catalog_sqlite(
        db_file
    )

    before = db_file.read_bytes()

    drift = (
        verifier.collect_plan_catalog_drift_from_db(
            db_file
        )
    )

    after = db_file.read_bytes()

    assert drift == []
    assert after == before


def test_external_sqlite_reader_detects_rpm_drift(
    tmp_path,
):

    import sqlite3

    db_file = tmp_path / "plans.db"

    _write_catalog_sqlite(
        db_file
    )

    connection = sqlite3.connect(
        db_file
    )

    try:

        connection.execute(
            """
            UPDATE plans
            SET quota_per_minute = 1000
            WHERE plan_code = 'general_month'
            """
        )

        connection.commit()

    finally:

        connection.close()

    drift = (
        verifier.collect_plan_catalog_drift_from_db(
            db_file
        )
    )

    assert any(
        item["plan_code"] == "general_month"
        and item["field"] == "quota_per_minute"
        and item["db"] == 1000
        and item["catalog"] == _catalog_policy_value("general_month", "quota_per_minute")
        for item in drift
    )


def test_project_root_resolves_db_path(
    tmp_path,
):

    project = tmp_path / "production"

    project.mkdir()

    (
        project / ".env"
    ).write_text(
        "DATA_DIR=runtime-data\n"
        "DB_FILE=runtime-data/main.db\n"
        "SOME_SECRET=do-not-output\n",
        encoding="utf-8",
    )

    expected = (
        project
        / "runtime-data"
        / "main.db"
    ).resolve()

    assert (
        verifier.resolve_project_db_file(
            project
        )
        == expected
    )


def test_production_preflight_contains_plan_gate():

    root = Path(
        __file__
    ).resolve().parents[1]

    text = (
        root
        / "tools"
        / "production_preflight.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "collect_plan_catalog_drift_from_db"
        in text
    )

    assert (
        'checks["plan_catalog"]'
        in text
    )

    assert (
        'and bool(checks["plan_catalog"]["ok"])'
        in text
    )
