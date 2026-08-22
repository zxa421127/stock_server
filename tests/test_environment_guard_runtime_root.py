from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.environment_guard import (
    collect_environment_errors,
    describe_environment,
)


def _settings(
    project_root: Path,
    runtime_root: Path,
    *,
    explicit_runtime_root: bool,
):
    project_root = project_root.resolve()
    runtime_root = runtime_root.resolve()

    return SimpleNamespace(
        ENVIRONMENT_GUARD_ENABLED=True,
        DEPLOYMENT_SLOT="test",
        BASE_DIR=project_root,
        EXPECTED_PROJECT_ROOT=str(
            project_root
        ),
        EXPECTED_RUNTIME_ROOT=(
            str(runtime_root)
            if explicit_runtime_root
            else ""
        ),
        APP_ENV="development",
        SERVER_HOST="127.0.0.1",
        SERVER_PORT=8898,
        EXPECTED_SERVER_PORT=8898,

        DATA_DIR=runtime_root / "data",

        DB_FILE=(
            runtime_root
            / "data"
            / "stock_server.db"
        ),

        LOG_DIR=runtime_root / "logs",

        AUDIT_SPOOL_DB_FILE=(
            runtime_root
            / "data"
            / "audit_spool.db"
        ),

        AUDIT_EMERGENCY_DIR=(
            runtime_root
            / "data"
            / "audit_emergency"
        ),

        FEISHU_SYNC_LOCK_FILE=(
            runtime_root
            / "data"
            / "feishu_sync.lock"
        ),

        ADMIN_API_TEST_RESULT_DIR=(
            runtime_root
            / "data"
            / "admin_api_test_results"
        ),

        ADMIN_API_TEST_SPEC_DIR=(
            runtime_root
            / "interface_specs"
        ),

        REDIS_URL=(
            "redis://127.0.0.1:6379/3"
        ),

        EXPECTED_REDIS_DB=3,

        REDIS_KEY_PREFIX=(
            "stock_server_test"
        ),

        EXPECTED_REDIS_KEY_PREFIX=(
            "stock_server_test"
        ),

        ADMIN_CLIENT_CERT_ADMIN_HOST=(
            "test-admin-api."
            "lifesupermarket.cn"
        ),

        EXPECTED_ADMIN_HOST=(
            "test-admin-api."
            "lifesupermarket.cn"
        ),

        API_DOC_STATUS_BASE_URL=(
            "http://127.0.0.1:8898"
        ),
    )


def test_legacy_runtime_boundary_is_project_root(
    tmp_path,
):
    project = tmp_path / "project"

    settings = _settings(
        project,
        project,
        explicit_runtime_root=False,
    )

    assert collect_environment_errors(
        settings,
        require_enabled=True,
    ) == []


def test_candidate_can_use_separate_runtime_root(
    tmp_path,
):
    project = tmp_path / "candidate-code"
    runtime = tmp_path / "runtime"

    settings = _settings(
        project,
        runtime,
        explicit_runtime_root=True,
    )

    assert collect_environment_errors(
        settings,
        require_enabled=True,
    ) == []


def test_runtime_path_escape_is_rejected(
    tmp_path,
):
    project = tmp_path / "candidate-code"
    runtime = tmp_path / "runtime"

    settings = _settings(
        project,
        runtime,
        explicit_runtime_root=True,
    )

    settings.DB_FILE = (
        project
        / "data"
        / "wrong.db"
    )

    errors = collect_environment_errors(
        settings,
        require_enabled=True,
    )

    assert any(
        "DB_FILE" in error
        and str(runtime.resolve()) in error
        for error in errors
    )


def test_relative_runtime_root_is_rejected(
    tmp_path,
):
    project = tmp_path / "candidate-code"

    settings = _settings(
        project,
        project,
        explicit_runtime_root=False,
    )

    settings.EXPECTED_RUNTIME_ROOT = (
        "relative-runtime"
    )

    errors = collect_environment_errors(
        settings,
        require_enabled=True,
    )

    assert any(
        "EXPECTED_RUNTIME_ROOT" in error
        for error in errors
    )


def test_project_root_guard_remains_separate(
    tmp_path,
):
    project = tmp_path / "candidate-code"
    runtime = tmp_path / "runtime"

    settings = _settings(
        project,
        runtime,
        explicit_runtime_root=True,
    )

    wrong_project = (
        tmp_path
        / "wrong-project"
    ).resolve()

    settings.EXPECTED_PROJECT_ROOT = str(
        wrong_project
    )

    errors = collect_environment_errors(
        settings,
        require_enabled=True,
    )

    assert any(
        str(wrong_project) in error
        for error in errors
    )


def test_description_reports_runtime_root(
    tmp_path,
):
    project = tmp_path / "candidate-code"
    runtime = tmp_path / "runtime"

    settings = _settings(
        project,
        runtime,
        explicit_runtime_root=True,
    )

    result = describe_environment(
        settings
    )

    assert (
        Path(
            result["project_root"]
        ).resolve()
        == project.resolve()
    )

    assert (
        Path(
            result["expected_runtime_root"]
        ).resolve()
        == runtime.resolve()
    )

    assert (
        Path(
            result["runtime_root"]
        ).resolve()
        == runtime.resolve()
    )


def test_config_has_expected_runtime_root_assignment():
    source = (
        Path(__file__).resolve().parents[1]
        / "config.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    tree = __import__("ast").parse(
        source
    )

    assignments = []

    for node in tree.body:
        if not isinstance(
            node,
            __import__("ast").Assign,
        ):
            continue

        for target in node.targets:
            if (
                isinstance(
                    target,
                    __import__("ast").Name,
                )
                and target.id
                == "EXPECTED_RUNTIME_ROOT"
            ):
                assignments.append(node)

    assert len(assignments) == 1
