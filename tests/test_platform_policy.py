from __future__ import annotations

import json
import re
from pathlib import Path

import config

from services.plan_catalog import (
    DEFAULT_PLANS,
)

from services.platform_policy import (
    ALLOWED_CONFIG_KEYS,
    expand_plans,
    load_platform_policy,
    managed_config,
    policy_file,
    waitress_backlog,
)


ROOT = Path(
    __file__
).resolve().parents[1]


def _normal(value):

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(k): _normal(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _normal(v)
            for v in value
        ]

    if isinstance(value, set):
        return sorted(
            _normal(v)
            for v in value
        )

    return value


def test_platform_policy_exists_and_loads():

    assert policy_file().is_file()

    policy = (
        load_platform_policy()
    )

    assert (
        policy["schema_version"]
        == 1
    )


def test_policy_matches_current_config_before_rewire():

    values = managed_config()

    assert (
        set(values)
        == set(
            ALLOWED_CONFIG_KEYS
        )
    )

    for key, expected in (
        values.items()
    ):

        assert hasattr(
            config,
            key,
        ), key

        actual = getattr(
            config,
            key,
        )

        assert (
            _normal(actual)
            == _normal(expected)
        ), key


def test_policy_plan_snapshot_matches_current_catalog():

    expanded = (
        expand_plans()
    )

    assert (
        _normal(expanded)
        == _normal(
            DEFAULT_PLANS
        )
    )


def test_waitress_backlog_snapshot_matches_launchers():

    assert (
        config.WAITRESS_BACKLOG
        == waitress_backlog()
    )

    for rel in (
        "run_waitress.py",
        "run_waitress_web_only.py",
    ):

        text = (
            ROOT
            .joinpath(rel)
            .read_text(
                encoding="utf-8-sig"
            )
        )

        assert (
            "backlog="
            "config.WAITRESS_BACKLOG"
            in text
        ), rel

        assert not re.search(
            r"\bbacklog\s*=\s*2048\b",
            text,
        ), rel


def test_policy_never_contains_environment_identity_or_secret_keys():

    policy = (
        load_platform_policy()
    )

    config_keys = set(
        policy["config"]
    )

    forbidden = {
        "APP_ENV",
        "DEPLOYMENT_SLOT",
        "ENVIRONMENT_GUARD_ENABLED",

        "SERVER_HOST",
        "SERVER_PORT",

        "EXPECTED_PROJECT_ROOT",
        "EXPECTED_RUNTIME_ROOT",
        "EXPECTED_SERVER_PORT",
        "EXPECTED_REDIS_DB",
        "EXPECTED_REDIS_KEY_PREFIX",

        "DATA_DIR",
        "DB_FILE",
        "LOG_DIR",

        "REDIS_URL",
        "REDIS_KEY_PREFIX",
        "REDIS_REQUIRED",

        "API_TOKEN_HASH_SECRET",

        "ADMIN_API_TEST_RESULT_DIR",
        "ADMIN_API_TEST_SPEC_DIR",

        "AUDIT_SPOOL_DB_FILE",

        "API_DOC_STATUS_BASE_URL",
        "API_DOC_STATUS_IN_PROCESS",

        "ADMIN_API_TEST_IN_PROCESS_WORKER",

        "TUSHARE_SPEC_MONITOR_IN_PROCESS",

        "MARKET_DATA_BACKGROUND_REFRESH_ENABLED",
        "MARKET_DATA_PREWARM_ENABLED",
    }

    assert not (
        config_keys
        & forbidden
    )


def test_policy_json_has_no_absolute_project_paths():

    raw = (
        policy_file()
        .read_text(
            encoding="utf-8-sig"
        )
    )

    lower = raw.lower()

    assert (
        "c:\\stockdata\\"
        not in lower
    )


def test_policy_is_plain_json():

    parsed = json.loads(
        policy_file().read_text(
            encoding="utf-8-sig"
        )
    )

    assert isinstance(
        parsed,
        dict,
    )
