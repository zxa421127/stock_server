from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import config

from services.platform_policy import (
    managed_config,
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


def test_all_managed_config_values_come_from_policy():

    expected = managed_config()

    for key, value in expected.items():

        assert hasattr(
            config,
            key,
        ), key

        assert (
            _normal(
                getattr(
                    config,
                    key,
                )
            )
            == _normal(value)
        ), key


def test_waitress_backlog_comes_from_policy():

    assert (
        config.WAITRESS_BACKLOG
        == waitress_backlog()
    )


def test_shared_environment_override_cannot_override_policy():

    expected = int(
        managed_config()[
            "API_MAX_RESPONSE_ROWS"
        ]
    )

    env = os.environ.copy()

    env[
        "API_MAX_RESPONSE_ROWS"
    ] = str(
        expected + 123
    )

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            "-c",
            (
                "import config;"
                "print("
                "config.API_MAX_RESPONSE_ROWS"
                ")"
            ),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        result.stderr
    )

    assert (
        result.stdout.strip()
        == str(expected)
    )


def test_environment_only_server_port_still_uses_environment():

    env = os.environ.copy()

    env["SERVER_PORT"] = "54321"

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            "-c",
            (
                "import config;"
                "print(config.SERVER_PORT)"
            ),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        result.stderr
    )

    assert (
        result.stdout.strip()
        == "54321"
    )


def test_secret_and_environment_identity_are_not_policy_managed():

    managed = set(
        managed_config()
    )

    forbidden = {
        "APP_ENV",
        "DEPLOYMENT_SLOT",
        "SERVER_HOST",
        "SERVER_PORT",
        "DB_FILE",
        "REDIS_URL",
        "REDIS_KEY_PREFIX",
        "API_TOKEN_HASH_SECRET",
    }

    assert not (
        managed
        & forbidden
    )


def test_waitress_launchers_have_no_numeric_backlog_policy():

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
        )

        assert "backlog=2048" not in text
