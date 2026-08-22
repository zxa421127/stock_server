# -*- coding: utf-8 -*-
"""TEST-only plan catalog synchronization CLI."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import config

from tools.db.plan_catalog_sync import (
    apply_field_delta,
    assert_delta_is_field_only,
    collect_delta,
)


ROOT = Path(
    __file__
).resolve().parents[2]


def _assert_test_runtime(
    project_root: Path,
) -> Path:

    root = project_root.resolve()

    if root != ROOT.resolve():
        raise RuntimeError(
            "project root must equal current TEST code root"
        )

    if str(
        getattr(
            config,
            "DEPLOYMENT_SLOT",
            "",
        )
    ).strip().lower() != "test":
        raise RuntimeError(
            "sync_test_plan_catalog requires "
            "DEPLOYMENT_SLOT=test"
        )


    db_file = Path(
        config.DB_FILE
    ).resolve()


    try:
        db_file.relative_to(
            root
        )
    except ValueError as exc:
        raise RuntimeError(
            "TEST DB must be inside TEST root"
        ) from exc


    if not db_file.is_file():
        raise RuntimeError(
            "TEST DB does not exist: "
            + str(db_file)
        )


    return db_file


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
    )

    args = parser.parse_args()


    project_root = (
        args.project_root
        .resolve()
    )


    db_file = (
        _assert_test_runtime(
            project_root
        )
    )


    delta = collect_delta(
        db_file
    )


    assert_delta_is_field_only(
        delta
    )


    print(
        "DEPLOYMENT_SLOT=test"
    )

    print(
        "TARGET_DB_MODE="
        + (
            "READ_WRITE"
            if args.apply
            else "READ_ONLY"
        )
    )

    print(
        "TARGET_DB_FILE="
        + str(
            db_file
        )
    )

    print(
        "PLAN_DELTA_COUNT="
        + str(
            len(delta)
        )
    )


    for item in delta:

        print(
            "PLAN_DELTA="
            + json.dumps(
                item,
                ensure_ascii=False,
                default=list,
                separators=(
                    ",",
                    ":",
                ),
            )
        )


    if not args.apply:

        print(
            "TEST_PLAN_SYNC_APPLIED=FALSE"
        )

        print(
            "TEST_PLAN_SYNC_DRY_RUN=PASS"
        )

        return 0


    if not delta:

        print(
            "TEST_PLAN_SYNC_CHANGED=FALSE"
        )

        print(
            "TEST_PLAN_SYNC_BACKUP_CREATED=FALSE"
        )

        print(
            "TEST_PLAN_SYNC_APPLIED=PASS"
        )

        return 0


    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )


    backup_db = (
        project_root.parent
        / "backups"
        / (
            "test-plan-policy-sync-"
            + stamp
        )
        / "stock_server.pre-policy-sync.db"
    )


    result = apply_field_delta(
        db_file,
        backup_db=backup_db,
    )


    print(
        "TEST_PLAN_SYNC_CHANGED="
        + str(
            bool(
                result[
                    "changed"
                ]
            )
        ).upper()
    )

    print(
        "TEST_PLAN_SYNC_CHANGED_PLAN_COUNT="
        + str(
            result[
                "changed_plan_count"
            ]
        )
    )

    print(
        "TEST_PLAN_SYNC_CHANGED_FIELD_COUNT="
        + str(
            result[
                "changed_field_count"
            ]
        )
    )

    print(
        "TEST_PLAN_SYNC_DRIFT_AFTER="
        + str(
            result[
                "drift_after"
            ]
        )
    )

    print(
        "TEST_PLAN_SYNC_BACKUP="
        + str(
            result[
                "backup_db"
            ]
        )
    )

    print(
        "TEST_PLAN_SYNC_APPLIED=PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
