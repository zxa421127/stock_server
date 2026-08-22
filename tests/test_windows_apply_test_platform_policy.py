from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]


SCRIPT = (
    ROOT
    / "deploy"
    / "windows"
    / "Apply-TestPlatformPolicy.ps1"
)


def _text():

    return SCRIPT.read_text(
        encoding="utf-8-sig"
    )


def test_policy_workflow_exists():

    assert SCRIPT.is_file()


def test_policy_workflow_uses_test_sync_cli():

    text = _text()

    assert (
        "-m tools.db.sync_test_plan_catalog"
        in text
    )

    assert "--apply" in text


def test_policy_workflow_verifies_catalog_after_apply():

    text = _text()

    apply_i = text.index(
        "--apply"
    )

    verify_i = text.index(
        "-m tools.db.verify_plan_catalog",
        apply_i,
    )

    assert verify_i > apply_i


def test_policy_workflow_runs_targeted_and_full_pytest():

    text = _text()

    assert (
        "POLICY TARGETED PYTEST"
        in text
    )

    assert (
        "-m pytest"
        in text
    )

    assert (
        "FULL PYTEST"
        in text
    )

    assert (
        "RELEASE_READY=TRUE"
        in text
    )


def test_policy_workflow_never_stops_production_or_caddy():

    text = _text().lower()

    forbidden = (
        "stop-service caddy",
        "restart-service caddy",
        "stop-scheduledtask",
        "disable-scheduledtask",
        "stop-process",
    )

    for value in forbidden:

        assert value not in text


def test_policy_workflow_never_writes_production_db():

    text = _text()

    assert (
        "tools.db.sync_test_plan_catalog"
        in text
    )

    assert (
        "sync_production_plan_catalog"
        not in text
    )


def test_policy_workflow_keeps_running_test_process():

    text = _text()

    assert (
        "TEST_SERVICE_RESTARTED=FALSE"
        in text
    )


def test_windows_policy_workflow_has_crlf_only():

    data = SCRIPT.read_bytes()

    assert b"\r\n" in data

    lone_lf = data.replace(
        b"\r\n",
        b"",
    )

    assert b"\n" not in lone_lf


def test_policy_workflow_parses_in_windows_powershell():

    env = os.environ.copy()

    env[
        "POLICY_WORKFLOW_PARSE_TARGET"
    ] = str(SCRIPT)


    command = (
        "$tokens=$null;"
        "$errors=$null;"
        "[System.Management.Automation.Language.Parser]"
        "::ParseFile("
        "$env:POLICY_WORKFLOW_PARSE_TARGET,"
        "[ref]$tokens,"
        "[ref]$errors"
        ") | Out-Null;"
        "if($errors.Count -ne 0){"
        "$errors | ForEach-Object {"
        "Write-Error $_.Message"
        "};"
        "exit 1"
        "};"
        "exit 0"
    )


    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command,
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
        + result.stdout
    )

