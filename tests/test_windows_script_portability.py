from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_SCRIPT_SUFFIXES = {".bat", ".cmd", ".ps1"}


def _windows_scripts() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in WINDOWS_SCRIPT_SUFFIXES
        and ".venv" not in path.parts
        and "docs" not in path.parts
    )


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_windows_scripts_use_crlf_without_lone_lf():
    bad: list[str] = []
    for path in _windows_scripts():
        raw = path.read_bytes()
        if b"\n" in raw and raw.count(b"\n") != raw.count(b"\r\n"):
            bad.append(str(path.relative_to(ROOT)))
    assert bad == []


def test_non_ascii_powershell_scripts_use_utf8_bom_for_windows_powershell_51():
    bad: list[str] = []
    for path in _windows_scripts():
        if path.suffix.lower() != ".ps1":
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        if any(ord(char) > 127 for char in text) and not raw.startswith(b"\xef\xbb\xbf"):
            bad.append(str(path.relative_to(ROOT)))
    assert bad == []


def test_repository_declares_windows_line_ending_rules():
    attributes = _read(".gitattributes")
    editorconfig = _read(".editorconfig")
    for pattern in ("*.bat text eol=crlf", "*.cmd text eol=crlf", "*.ps1 text eol=crlf"):
        assert pattern in attributes
    assert "[*.{bat,cmd,ps1}]" in editorconfig
    assert "end_of_line = crlf" in editorconfig


def test_active_windows_scripts_use_waitress_entrypoint_not_app_py():
    bad: list[str] = []
    for path in _windows_scripts():
        text = path.read_text(encoding="utf-8-sig").lower()
        if "python app.py" in text:
            bad.append(str(path.relative_to(ROOT)))
    assert bad == []


def test_six_plan_verifier_references_existing_test_module():
    text = _read("scripts/windows/verify_six_plan_test_suite_fix.bat")
    assert "tests.test_e2e_two_tier_tokens" in text
    assert "tests.test_e2e_tests_two_tier_tokens" not in text
    assert (ROOT / "tests/test_e2e_two_tier_tokens.py").is_file()


def test_e2e_batch_files_can_run_non_interactively_and_preserve_exit_code():
    for path in sorted((ROOT / "e2e_tests").rglob("*.bat")):
        text = path.read_text(encoding="utf-8-sig")
        assert "STOCK_TEST_NO_PAUSE" in text, path
        assert "exit /b %EXIT_CODE%" in text, path


def test_membership_tester_supports_remote_base_url_and_isolated_token_output(monkeypatch, tmp_path):
    from tools import membership_tester

    monkeypatch.setenv("STOCK_TEST_BASE_URL", "https://test-api.lifesupermarket.cn/")
    monkeypatch.setenv("STOCK_TEST_TOKEN_FILE", str(tmp_path / "tokens.json"))
    assert membership_tester.resolve_base_url(None) == "https://test-api.lifesupermarket.cn"
    assert membership_tester.resolve_token_file(None) == tmp_path / "tokens.json"


def test_e2e_common_supports_isolated_result_and_token_paths():
    text = _read("e2e_tests/core/auto_tests/common.py")
    assert "STOCK_TEST_RESULT_DIR" in text
    assert "STOCK_TEST_TOKEN_FILE" in text
    assert "_resolve_runtime_path" in text
    assert "必须位于当前测试项目目录内" in text
    assert "test-api.lifesupermarket.cn" in text


def test_scheduled_task_nginx_prefix_uses_parameter_value():
    text = _read("deploy/windows/register-scheduled-tasks.ps1")
    assert "$nginxPrefix" in text
    assert "C:/stockdata/nginx" not in text


def test_dependency_installer_targets_and_checks_python_312():
    text = _read("deploy/windows/install-dependencies.ps1")
    assert '[string]$PythonVersion = "3.12"' in text
    assert "-$PythonVersion" in text
    assert "sys.version_info" in text


def test_production_verifier_can_run_tests_from_separate_source_tree():
    text = _read("deploy/windows/verify-production.ps1")
    assert "$TestSourceRoot" in text
    assert "生产发布包通常不包含tests" in text


def test_ntfs_permissions_include_configured_runtime_paths():
    text = _read("deploy/windows/set-ntfs-permissions.ps1")
    assert "AUDIT_SPOOL_DB_FILE" in text
    assert "AUDIT_EMERGENCY_DIR" in text
    assert "FEISHU_SYNC_LOCK_FILE" in text
    assert "LOG_DIR" in text

def test_runtime_and_test_scripts_require_project_virtualenv():
    allowed = {Path("deploy/windows/install-dependencies.ps1")}
    bad: list[str] = []
    for path in _windows_scripts():
        rel = path.relative_to(ROOT)
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8-sig").lower()
        if 'set "python_exe=python"' in text or "where python" in text:
            bad.append(str(rel))
    assert bad == []

def test_e2e_documentation_does_not_publish_waitress_port():
    text = _read("e2e_tests/README_CN.txt")
    assert "公网地址：http://" not in text
    assert ":8899" not in "\n".join(
        line for line in text.splitlines() if "公网" in line
    )

def test_gitignore_excludes_isolated_runtime_and_test_directories():
    text = _read(".gitignore")
    for entry in ("data-dev/", "data-test/", "logs-dev/"):
        assert entry in text

def test_test_tools_load_dotenv_before_reading_test_environment():
    interface_text = _read("tools/interface_tester.py")
    common_text = _read("e2e_tests/core/auto_tests/common.py")
    assert "load_dotenv" in interface_text
    assert "load_dotenv" in common_text



def test_test_tools_default_to_isolated_data_test_directory():
    membership_text = _read("tools/membership_tester.py")
    interface_text = _read("tools/interface_tester.py")
    common_text = _read("e2e_tests/core/auto_tests/common.py")
    assert '"data-test"' in membership_text
    assert '"data-test"' in interface_text
    assert 'ROOT / "data-test"' in common_text


def test_ntfs_script_resolves_relative_runtime_paths_under_project_root():
    text = _read("deploy/windows/set-ntfs-permissions.ps1")
    assert "[IO.Path]::IsPathRooted" in text
    assert "Join-Path $ProjectRoot" in text
    assert "Resolve-ProjectPath" in text


def test_e2e_documentation_uses_runtime_catalog_instead_of_fixed_provider_counts():
    text = _read("e2e_tests/README_CN.txt")
    assert "以服务器运行时目录为准" in text
    assert "开盘啦1个" not in text


def test_scheduled_task_caddy_uses_parameter_values_and_can_skip_proxy_task():
    text = _read("deploy/windows/register-scheduled-tasks.ps1")
    assert "$CaddyRoot" in text
    assert "$CaddyConfig" in text
    assert "$SkipReverseProxyTask" in text
    assert "C:/caddy" not in text


def test_production_verifier_uses_explicit_reverse_proxy_type():
    text = _read("deploy/windows/verify-production.ps1")
    assert '[ValidateSet("Nginx", "Caddy", "None")]' in text
    assert 'switch ($ReverseProxyType)' in text


def test_e2e_and_test_launchers_have_no_implicit_production_base_url():
    paths = list((ROOT / "e2e_tests").rglob("*.bat")) + [
        ROOT / "scripts/windows/run_interface_test.bat",
        ROOT / "scripts/windows/run_membership_test.bat",
    ]
    for path in paths:
        content = path.read_text(encoding="utf-8-sig")
        assert "STOCK_TEST_BASE_URL must be set explicitly" in content, path
        assert "127.0.0.1:8899" not in content, path


def test_membership_tester_has_no_base_url_default_and_refuses_production(monkeypatch):
    from tools import membership_tester

    monkeypatch.delenv("STOCK_TEST_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="显式设置"):
        membership_tester.resolve_base_url(None)
    with pytest.raises(ValueError, match="生产端口"):
        membership_tester.resolve_base_url("http://127.0.0.1:8899")
    assert membership_tester.resolve_base_url("http://127.0.0.1:8898") == "http://127.0.0.1:8898"
    assert membership_tester.resolve_base_url("https://test-api.lifesupermarket.cn") == "https://test-api.lifesupermarket.cn"
    with pytest.raises(ValueError, match="只允许测试实例"):
        membership_tester.resolve_base_url("https://unknown-test.example.com")


def test_interface_and_load_test_require_explicit_targets():
    interface_text = _read("tools/interface_tester.py")
    load_text = _read("tools/load_test.py")
    assert 'DEFAULT_BASE_URL = os.getenv("STOCK_TEST_BASE_URL", "")' in interface_text
    assert "ALLOW-PRODUCTION-INTERFACE-TEST" in interface_text
    assert "test-api.lifesupermarket.cn" in interface_text
    assert "_assert_path_within_project" in interface_text
    assert 'parser.add_argument("--url", required=True)' in load_text
    assert "127.0.0.1:8899" not in load_text


def test_scheduled_tasks_default_unselected_workers_to_disabled():
    text = _read("deploy/windows/register-scheduled-tasks.ps1")
    assert "EnabledWorkers" in text
    assert "Disable-ScheduledTask" in text
    assert "RestartCount 3" in text
    assert "EnabledWorkers" in text
    assert "$enabledWorkersSpecified" in text
    assert "保留旧任务的启用/禁用状态" in text
    assert "已停止并禁用现有可选任务" in text



def test_e2e_and_interface_test_targets_use_explicit_allowlists(monkeypatch):
    from e2e_tests.core.auto_tests.common import validate_test_base_url
    from tools.interface_tester import validate_interface_test_base_url

    assert validate_test_base_url("http://127.0.0.1:8898") == "http://127.0.0.1:8898"
    assert validate_test_base_url("https://test-api.lifesupermarket.cn") == "https://test-api.lifesupermarket.cn"
    with pytest.raises(RuntimeError, match="只允许测试实例"):
        validate_test_base_url("https://unknown-test.example.com")
    with pytest.raises(RuntimeError, match="不能包含"):
        validate_test_base_url("https://test-api.lifesupermarket.cn/path")

    assert validate_interface_test_base_url("http://127.0.0.1:8898") == "http://127.0.0.1:8898"
    with pytest.raises(ValueError, match="只允许"):
        validate_interface_test_base_url("https://unknown-test.example.com")
    monkeypatch.setenv("STOCK_TEST_PRODUCTION_CONFIRM", "ALLOW-PRODUCTION-INTERFACE-TEST")
    assert validate_interface_test_base_url("https://api.lifesupermarket.cn") == "https://api.lifesupermarket.cn"


def test_e2e_runtime_paths_reject_locations_outside_project(tmp_path):
    from e2e_tests.core.auto_tests import common

    with pytest.raises(RuntimeError, match="必须位于当前测试项目目录内"):
        common._resolve_runtime_path(
            str(tmp_path / "outside.json"),
            name="STOCK_TEST_TOKEN_FILE",
            default=common.ROOT / "data-test" / "membership_test_tokens.json",
        )
